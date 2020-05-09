import html
import os
import re


##
# Functions for validating basic types from H5P library semantics.
##
class H5PContentValidator:
    allowed_styleable_tags = ["span", "p", "div"]

    ##
    # Constructor for the H5PContentValidator
    ##
    def __init__(self, framework, core):
        self.h5pF = framework
        self.h5pC = core
        self.typeMap = {"text": "validateText", "number": "validateNumber", "boolean": "validateBoolean",
                        "list": "validateList", "group": "validateGroup", "file": "validateFile",
                        "image": "validateImage", "video": "validateVideo", "audio": "validateAudio",
                        "select": "validateSelect", "library": "validateLibrary"}
        self.nextWeight = 1

        # Keep track of the libraries we load to avoid loading it multiple
        # times.
        self.libraries = dict()

        # Keep track of all dependencies for the given content.
        self.dependencies = dict()

    ##
    # Get the flat dependency tree.
    ##
    def getDependencies(self):
        return self.dependencies

    ##
    # Validate given text value against text semantics.
    ##
    def validateText(self, text, semantics):
        if not isinstance(text, str):
            text = ''

        if 'tags' in semantics:
            tags = ['div', 'span', 'p', 'br'] + semantics['tags']

            if 'table' in tags:
                tags += ['tr', 'td', 'th', 'colgroup', 'thead', 'tbody', 'tfoot']
            if 'b' in tags and 'strong' not in tags:
                tags.append('strong')
            if 'i' in tags and 'em' not in tags:
                tags.append('em')
            if 'ul' in tags or 'ol' in tags and 'li' not in tags:
                tags.append('li')
            if 'del' in tags or 'strike' in tags and 's' not in tags:
                tags.append('s')

            stylePatterns = list()
            if 'font' in semantics:
                if 'size' in semantics['font']:
                    stylePatterns.append('(?i)^font-size: *[0-9.]+(em|px|%) *;?$')
                if 'family' in semantics['font']:
                    stylePatterns.append('(?i)^font-family: *[a-z0-9," ]+;?$')
                if 'color' in semantics['font']:
                    stylePatterns.append('(?i)^color: *(#[a-f0-9]{3}[a-f0-9]{3}?|rgba?\([0-9, ]+\)) *;?$')
                if 'background' in semantics['font']:
                    stylePatterns.append('(?i)^background-color: *(#[a-f0-9]{3}[a-f0-9]{3}?|rgba?\([0-9, ]+\)) *;?$')
                if 'spacing' in semantics['font']:
                    stylePatterns.append('(?i)^letter-spacing: *[0-9.]+(em|px|%) *;?$')
                if 'height' in semantics['font']:
                    stylePatterns.append('(?i)^line-height: *[0-9.]+(em|px|%|) *;?$')

            stylePatterns.append('(?i)^text-align: *(center|left|right);?$')

            # text = self.filterXss(text, tags, stylePatterns)
        else:
            text = html.escape(text, True)

        if 'maxLength' in semantics:
            text = text[0:semantics['maxLength']]

        if not text == '' and 'optional' in semantics and 'regexp' in semantics:
            pattern = semantics['regexp']['modifiers'] if 'modifiers' in semantics['regexp'] else ''
            if not re.search(pattern, text):
                print(('Provided string is not valid according to regexp in semantics. (value: %s, regexp: %s)' % (
                    text, pattern)))
                text = ''

    ##
    # Validates content files
    ##
    def validateContentFiles(self, contentPath, isLibrary=False):
        if self.h5pC.disableFileCheck:
            return True

        # Scan content directory for files, recurse into sub directories.
        files = list(set(os.listdir(contentPath)).difference([".", ".."]))
        valid = True
        from h5pp.h5p.library.H5PCore import H5PCore
        whitelist = self.h5pF.getWhitelist(isLibrary, H5PCore.defaultContentWhitelist,
                                           H5PCore.defaultLibraryWhitelistExtras)

        wl_regex = "^.*\.(" + re.sub(" ", "|", whitelist) + ")$"

        for f in files:
            file_path = contentPath / f
            if os.path.isdir(file_path):
                valid = self.validateContentFiles(file_path, isLibrary) and valid
            else:
                if not re.search(wl_regex, f.lower()):
                    print(("File \"%s\" not allowed. Only files with the following extension are allowed : %s" % (
                        f, whitelist)))
                    valid = False

        return valid

    ##
    # Validate given value against number semantics
    ##
    def validateNumber(self, number, semantics):
        # Validate that number is indeed a number
        if not isinstance(number, int):
            number = 0

        # Check if number is within valid bounds. Move withing bounds if not.
        if 'min' in semantics and number < semantics['min']:
            number = semantics['min']
        if 'max' in semantics and number > semantics['max']:
            number = semantics['max']

        # Check if number if withing allowed bounds even if step value is set.
        if 'step' in semantics:
            text_number = number - (semantics['min'] if 'min' in semantics else 0)
            rest = text_number % semantics['step']
            if rest != 0:
                number = number - rest

        # Check if number has proper number of decimals.
        if 'decimals' in semantics:
            number = round(number, semantics['decimals'])

    ##
    # Validate given value against boolean semantics
    ##
    def validateBoolean(self, boolean, semantics):
        return isinstance(boolean, bool)

    ##
    # Validate select values
    ##
    def validateSelect(self, select, semantics):
        optional = semantics['optional'] if 'optional' in semantics else False
        strict = False
        from h5pp.h5p.library.H5PCore import H5PCore
        if 'options' in semantics and not H5PCore.empty(semantics['options']):
            # We have a strict set of options to choose from.
            strict = True
            options = dict()
            for option in semantics['options']:
                options[option['value']] = True

        if 'multiple' in semantics and semantics['multiple']:
            # Multi-choice generates array of values. Test each one against valid
            # options, if we are strict. First make sure we are working on an
            # array.
            if not isinstance(select, list):
                select = list(select)

            for key, value in select:
                if strict and not optional and not options[value]:
                    print("Invalid selected option in multi-select.")
                    del select[key]
                else:
                    select[key] = html.escape(value, True)
        else:
            # Single mode. If we get an array in here, we chop off the first
            # element and use that instead.
            if isinstance(select, list):
                select = select[0]

            if strict and not optional and not options[select]:
                print("Invalid selected option in select.")
                select = semantics[options[0]['value']]

            select = html.escape(select, True)

    ##
    # Validate given list value against list semantics.
    # Will recurse into validating each item in the list according to the type.
    ##
    def validateList(self, plist, semantics):
        field = semantics['field']
        func = self.typeMap[field['type']]

        if not isinstance(plist, list):
            plist = list()

        # Validate each element in list.
        for value in plist:
            eval('self.' + func + '(value, field)')

        if len(plist) == 0:
            plist = None

    ##
    # Validate a file like object, such as video, image, audio and file.
    ##
    def validateFilelike(self, f, semantics, typeValidKeys=None):
        if typeValidKeys is None:
            typeValidKeys = []

        # Do not allow to use files from other content folders.
        matches = re.search(self.h5pC.relativePathRegExp, f['path'])
        if matches:
            f['path'] = matches.group(4)

        # Make sure path and mime does not have any special chars
        f['path'] = html.escape(f['path'], True)
        if 'mime' in f:
            f['mime'] = html.escape(f['mime'], True)

        # Remove attributes that should not exist, they may contain JSON escape
        # code.
        valid_keys = ["path", "mime", "copyright"] + typeValidKeys
        if 'extraAttributes' in semantics:
            valid_keys = valid_keys + semantics['extraAttributes']

        self.filterParams(f, valid_keys)

        if 'width' in f:
            f['width'] = int(f['width'])

        if 'height' in f:
            f['height'] = int(f['height'])

        if 'codecs' in f:
            f['codecs'] = html.escape(f['codecs'], True)

        if 'quality' in f:
            if not isinstance(f['quality'], object) or 'level' not in f['quality'] or 'label' not in f['quality']:
                del f['quality']
            else:
                self.filterParams(f['quality'], ["level", "label"])
                f['quality']['level'] = int(f['quality']['level'])
                f['quality']['label'] = html.escape(f['quality']['label'], True)

        if 'copyright' in f:
            self.validateGroup(f['copyright'], self.getCopyrightSemantics())

    ##
    # Validate given file data
    ##
    def validateFile(self, f, semantics):
        self.validateFilelike(f, semantics)

    ##
    # Validate given image data
    ##
    def validateImage(self, image, semantics):
        self.validateFilelike(image, semantics, ["width", "height", "originalImage"])

    ##
    # Validate given video data
    ##
    def validateVideo(self, video, semantics):
        for variant in video:
            self.validateFilelike(variant, semantics, ["width", "height", "codecs", "quality"])

    ##
    # Validate given audio data
    ##
    def validateAudio(self, audio, semantics):
        for variant in audio:
            self.validateFilelike(variant, semantics)

    ##
    # Validate given group value against group semantics
    ##
    def validateGroup(self, group, semantics, flatten=True):
        # Groups with just one field are compressed in the editor to only output
        # the child content. (Exemption for fake groups created by
        # "validateBySemantics" above)
        func = None
        field = None
        is_sub_content = True if 'isSubContent' in semantics and semantics['isSubContent'] else False

        if len(semantics['fields']) == 1 and flatten and not is_sub_content:
            field = semantics['fields'][0]
            func = self.typeMap[field['type']]
            eval('self.' + func + '(group, field)')
        else:
            for key, value in list(group.items()):
                if is_sub_content and key == 'subContentId':
                    continue

                found = False
                foundField = None
                for field in semantics['fields']:
                    if field['name'] == key:
                        if 'optional' in semantics:
                            field['optional'] = True
                        func = self.typeMap[field['type']]
                        found = True
                        foundField = field
                        break
                if found:
                    if func:
                        eval('self.' + func + '(value, foundField)')
                        if value is None:
                            del key
                    else:
                        print(('H5P internal error: unknown content type "%s" in semantics. Removing content !' % field[
                            'type']))
                        del key
                else:
                    del key

        if "optional" not in semantics:
            if group is None:
                return

            for field in semantics['fields']:
                if 'optional' not in field:
                    if field['name'] not in group:
                        print(('No value given for mandatory field : {}'.format(field['name'])))

    ##
    # Validate given library value against library semantics.
    # Check if provided library is withing allowed options.
    #
    # Will recurse into validating the library"s semantics too.
    ##

    def validateLibrary(self, value, semantics):
        if "library" not in value:
            value = None
            return

        if not value['library'] in semantics['options']:
            message = None
            machine_name_array = value['library'].split(' ')
            machine_name = machine_name_array[0]
            for semanticsLibrary in semantics['options']:
                semantics_machine_name_array = semanticsLibrary.split(' ')
                semantics_machine_name = semantics_machine_name_array[0]
                if machine_name == semantics_machine_name:
                    message = 'The version of the H5P library %s used in the content is not valid. ' \
                              'Content contains %s, but it should be %s.' \
                              % (machine_name, value['library'], semanticsLibrary)

            if message is None:
                message = 'The H5P library %s used in the content is not valid.' % value['library']
                print(message)
                value = None
                return

        if not value['library'] in self.libraries:
            lib_spec = self.h5pC.library_from_string(value['library'])
            library = self.h5pC.load_library(lib_spec['machine_name'], lib_spec['majorVersion'], lib_spec['minorVersion'])
            library['semantics'] = self.h5pC.load_library_semantics(lib_spec['machine_name'], lib_spec['majorVersion'],
                                                                    lib_spec['minorVersion'])
            self.libraries[value['library']] = library
        else:
            library = self.libraries[value['library']]

        self.validateGroup(value['params'], {'type': 'group', 'fields': library['semantics'], }, False)
        valid_keys = ['library', 'params', 'subContentId']
        if 'extraAttributes' in semantics:
            valid_keys = valid_keys + semantics['extraAttributes']
        self.filterParams(value, valid_keys)

        if ("subContentId" in value and not re.search(
                '(?i)^\{?[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\}?$', value["subContentId"])):
            del (value["subContentId"])

        dep_key = 'preloaded-' + library['machine_name']
        if dep_key not in self.dependencies:
            self.dependencies[dep_key] = {'library': library, 'type': 'preloaded'}
            self.nextWeight = self.h5pC.find_library_dependencies(self.dependencies, library, self.nextWeight)
            self.nextWeight += 1
            self.dependencies[dep_key]['weight'] = self.nextWeight

    ##
    # Check params for a whitelist of allowed properties
    ##
    def filterParams(self, params, whitelist):
        for key, value in list(params.items()):
            if key not in whitelist:
                del params[key]

    ##
    # Prevent cross-site-scripting (XSS) vulnerabilities
    ##
    def filterXss(self, string, allowedTags=None, allowedStyles=False):
        if allowed_tags is None:
            allowed_tags = ['a', 'em', 'strong', 'cite', 'blockquote', 'code', 'ul', 'ol', 'li', 'dl', 'dt', 'dd']

        if len(string) == 0:
            return string

        # Only operate on valid UTF-8 strings
        if not re.search('(?us)^.', string):
            return ''

        # Remove NULL characters (ignored by some browsers)
        string = string.replace(chr(0), '')
        # Remove Netscape 4 JS entities
        string = re.sub('%&\s*\{[^}]*(\)\s*;?|$)%', '', string)

        # Defuse all HTML entities
        string = string.replace('&', '&amp;')
        # Change back only well-formed entities in our whitelist
        # Deciman numeric entities
        string = re.sub('&amp;#([0-9]+;)', '&#\1', string)
        # Hexadecimal numeric entities
        string = re.sub('&amp;#[Xx]0*((?:[0-9A-Fa-f]{2})+;)', '&#x\1', string)
        # Named entities
        string = re.sub('&amp;([A-Za-z][A-Za-z0-9]*;)', '&\1', string)

        return re.sub('%(<(?=[^a-zA-Z!/])|<!--.*?-->|<[^>]*(>|$)|>)%x',
                      lambda match: self.filterXssSplit(match, allowed_tags, allowedStyles), string)

    ##
    # Process an HTML tag
    ##
    def filterXssSplit(self, match, allowedTags, allowedStyles):
        string = match[1]

        if string[0:1] != '<':
            # We matched a lone ">" character
            return '&gt;'
        elif len(string) == 1:
            # We matched a lone "<" character
            return '&lt;'

        matches = re.search('%^<\s*(/\s*)?([a-zA-Z0-9\-]+)([^>]*)>?|(<!--.*?-->)$%', string)
        if not matches:
            # Seriously malformed
            return ''

        slash = matches.group(0).strip()
        elem = matches.group(1)
        attr_list = matches.group(2)
        comment = matches.group(3)

        if comment:
            elem = '!--'

        if not elem.lower() in allowedTags:
            # Disallowed HTML element
            return ''

        if comment:
            return comment

        if slash != '':
            return '</' + elem + '>'

        # Is there a closing XHTML slash at the end of the attributes ?
        attr_list = re.sub('%(\s?)/\s*$%', '\1', attr_list, -1)
        xhtml_slash = '/' if attr_list else ''

        # Clean up attributes
        attr2 = ' '.join(
            self.filterXssAttributes(attr_list, allowedStyles if elem in self.allowed_styleable_tags else False))
        attr2 = re.sub('[<>]', '', attr2)
        attr2 = ' ' + attr2 if len(attr2) else ''

        return '<' + elem + attr2 + xhtml_slash + '>'

    def getCopyrightSemantics(self):

        semantics = {"name": "copyright", "type": "group", "label": "Copyright information", "fields": [
            {"name": "title", "type": "text", "label": "Title", "placeholder": "La Gioconda", "optional": 'true'},
            {"name": "author", "type": "text", "label": "Author", "placeholder": "Leonardo da Vinci",
                "optional": 'true'},
            {"name": "year", "type": "text", "label": "Year(s)", "placeholder": "1503 - 1517", "optional": 'true'},
            {"name": "source", "type": "text", "label": "Source",
                "placeholder": "http://en.wikipedia.org/wiki/Mona_Lisa", "optional": 'true',
                "regexp": {"pattern": "^http[s]?://.+", "modifiers": "i"}},
            {"name": "license", "type": "select", "label": "License", "default": "U",
                "options": [{"value": "U", "label": "Undisclosed"}, {"value": "CC BY", "label": "Attribution 4.0"},
                            {"value": "CC BY-SA", "label": "Attribution-ShareAlike 4.0"},
                            {"value": "CC BY-ND", "label": "Attribution-NoDerivs 4.0"},
                            {"value": "CC BY-NC", "label": "Attribution-NonCommercial 4.0"},
                            {"value": "CC BY-NC-SA", "label": "Attribution-NonCommercial-ShareAlike 4.0"},
                            {"value": "CC BY-NC-ND", "label": "Attribution-NonCommercial-NoDerivs 4.0"},
                            {"value": "GNU GPL", "label": "General Public License v3"},
                            {"value": "PD", "label": "Public Domain"},
                            {"value": "ODC PDDL", "label": "Public Domain Dedication and Licence"},
                            {"value": "CC PDM", "label": "Public Domain Mark"},
                            {"value": "C", "label": "Copyright"}
                            ]
             }
        ]}
        return semantics
