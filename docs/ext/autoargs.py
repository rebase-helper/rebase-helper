import re

from argparse import ArgumentParser, SUPPRESS

from docutils import nodes
from docutils.statemachine import StringList
from docutils.parsers.rst import Directive
from docutils.parsers.rst.directives import flag, positive_int, unchanged, unchanged_required
from sphinx import addnodes
from sphinx.errors import SphinxError


class AutoArgsError(SphinxError):
    """Base class for AutoArgs errors"""
    category = 'autoargs extension error'


class AutoArgsDirective(Directive):
    """
    Generates program synopsis, description and option list from
    pre-configured ArgumentParser instance

    All sections and every option description can be extended with
    custom content

    :param function: function returning pre-configured ArgumentParser instance
    :param module: module containing the function
    :param program_name: name of the program
    :param synopsis_max_width: maximal width of synopsis (number of characters)
    :param ignore_option_groups: do not render options in groups
    """
    option_spec = dict(function=unchanged_required,
                       module=unchanged_required,
                       program_name=unchanged,
                       synopsis_max_width=positive_int,
                       ignore_option_groups=flag)
    has_content = True
    synopsis_max_width = None
    ignore_option_groups = False

    @staticmethod
    def _get_program_name(parser):
        """Return sanitized program name"""
        return re.sub(r'\s+', '-', parser.prog)

    def _decorate_references(self, text):
        """
        Decorate string conversion specifiers which are used as references
        to program name or action properties
        """
        # python string conversion specifier regex
        template = r'(%\({}\)[#0\- +]?(\d+|\*)?(\.(\d+|\*))?[hlL]?[diouxXeEfFgGcrs%])'
        replacements = dict(prog=r'\\ :program:`\1`\\ ',
                            default=r'\\ ``\1``\\ ',
                            metavar=r'\\ ``\1``\\ ')
        for k, v in replacements.items():
            text = re.sub(template.format(k), v, text or '')
        return text

    def _format_synopsis(self, synopsis):
        """
        Format synopsis so it fits into maximal width

        :param synopsis: synopsis text divided into non-breakable parts
        :return: list of lines of formatted synopsis text
        """
        def len_plain(text):
            text = re.sub(r':\w+:`(.+?)`', r'\1', text)
            text = re.sub(r'([`*]{1,2})(.+?)\1', r'\2', text)
            text = re.sub(r'\\ ', '', text)
            return len(text)
        result = []
        line = [synopsis.pop(0)]
        synopsis.reverse()
        while synopsis:
            line.append(synopsis.pop())
            if len_plain(' '.join(line)) > self.synopsis_max_width and len(line) > 2:
                synopsis.append(line.pop())
                result.append(' '.join(line))
                line = [' ']
        result.append(' '.join(line))
        return ['| {}'.format(l) for l in result]

    @staticmethod
    def _get_delimiter(fmt, action):
        """
        Extract delimiter from usage string formatted
        by specified HelpFormatter
        """
        if not action.option_strings or action.nargs == 0:
            return None
        else:
            usage = fmt._format_actions_usage([action], [])
            option_string = action.option_strings[0]
            idx = usage.find(option_string)
            if idx == -1:
                return None
            return usage[idx + len(option_string)]

    @classmethod
    def _get_option_group(cls, fmt, action):
        """
        Extract group of option properties from specified action

        :param fmt: HelpFormatter to use
        :param action: source Action
        :return: list of option properties
        """
        result = []
        if not action.option_strings:
            # positional option
            metavar, = fmt._metavar_formatter(action, action.dest)(1)
            args = fmt._format_args(action, action.dest)
            optional = False
            if args[0] == '[' and args[-1] == ']':
                args = args[1:-1]
                optional = True
            result.append(dict(name=metavar, synopsis=args, optional=optional))
        else:
            if action.nargs == 0:
                # option without arguments
                for option_string in action.option_strings:
                    result.append(dict(name=option_string, synopsis=option_string))
            else:
                # option with arguments
                args = fmt._format_args(action, action.dest.upper())
                delim = cls._get_delimiter(fmt, action)
                for option_string in action.option_strings:
                    result.append(dict(name=option_string, args=delim+args, synopsis=option_string+delim+args))
        return result

    def _build_option_description(self, fmt, action, custom_content):
        """
        Build description of program option

        :param fmt: HelpFormatter to use
        :param action: source Action
        :param custom_content: custom content for option
        :return: node forming option description
        """
        action.help = self._decorate_references(action.help)
        help = fmt._expand_help(action)
        result = nodes.container()
        self.state.nested_parse(StringList([help]), 0, result)
        if custom_content:
            if custom_content['action'] == 'append':
                result.extend(custom_content['content'].children)
            elif custom_content['action'] == 'prepend':
                result[0:0] = custom_content['content'].children
            elif custom_content['action'] == 'replace':
                result[:] = custom_content['content']
        return result

    def _build_option_index(self, progname, ids, names, synopses):
        """
        Build index for program option and register it in the environment

        :param progname: program name
        :param ids: list of all option ids
        :param names: list of all option names
        :param synopses: list of all option synopses
        :return: index node
        """
        env = self.state.document.settings.env
        result = addnodes.index(entries=[])
        for id, name, synopsis in zip(ids, names, synopses):
            env.domaindata['std']['progoptions'][progname, name] = env.docname, id
            if synopsis != name:
                env.domaindata['std']['progoptions'][progname, synopsis] = env.docname, id
            pair = '{} command line option; {}'.format(progname, ', '.join(synopses))
            result['entries'].append(('pair', pair, id, '', None))
        return result

    def _build_option(self, parser, action, custom_content):
        """
        Build single program option

        :param parser: pre-configured ArgumentParser instance
        :param action: source Action
        :param custom_content: custom content for options
        :return: node forming program option
        """
        def get_id(progname, name):
            id = 'cmdoption-{}'.format(progname)
            if not name.startswith('-'):
                id += '-arg-'
            id += name
            return id
        fmt = parser._get_formatter()
        result = nodes.container()
        signature = addnodes.desc_signature(ids=[], allnames=[], first=False)
        self.state.document.note_explicit_target(signature)
        description = self._build_option_description(fmt, action, custom_content)
        content = addnodes.desc_content('', description)
        result.append(addnodes.desc('', signature, content, objtype='option'))
        progname = self._get_program_name(parser)
        synopses = []
        for option in self._get_option_group(fmt, action):
            signature['ids'].append(get_id(progname, option['name']))
            signature['allnames'].append(option['name'])
            signature.append(addnodes.desc_name(text=option['name']))
            if 'args' in option:
                signature.append(addnodes.desc_addname(text=option['args']))
            signature.append(addnodes.desc_addname(text=', '))
            synopses.append(option['synopsis'])
        signature.pop()
        index = self._build_option_index(progname, signature['ids'], signature['allnames'], synopses)
        result.append(index)
        return result

    def _build_program_synopsis(self, parser):
        """
        Build program synopsis

        :param parser: pre-configured ArgumentParser instance
        :return: node forming program synopsis
        """
        fmt = parser._get_formatter()
        groups = []
        for action in parser._get_optional_actions() + parser._get_positional_actions():
            if action.help is SUPPRESS:
                continue
            in_group = False
            for group in parser._mutually_exclusive_groups:
                if action in group._group_actions:
                    in_group = True
                    if action == group._group_actions[0]:
                        groups.append(dict(actions=group._group_actions, required=group.required))
            if not in_group:
                groups.append(dict(actions=[action], required=action.required))
        synopsis = ['\\ :program:`{}`\\ '.format(parser.prog)]
        for group in groups:
            usages = []
            for action in group['actions']:
                option = self._get_option_group(fmt, action)[0]
                if option.get('optional') and len(group['actions']) == 1:
                    group['required'] = False
                usage = '\\ :option:`{}`\\ '.format(option['synopsis'])
                usages.append(usage)
            if not group['required']:
                synopsis.append('[{}]'.format(' | '.join(usages)))
            elif len(group['actions']) > 1:
                synopsis.append('({})'.format(' | '.join(usages)))
            else:
                synopsis.append('{}'.format(usages[0]))
        synopsis = self._format_synopsis(synopsis)
        paragraph = nodes.paragraph()
        self.state.nested_parse(StringList(synopsis), 0, paragraph)
        return nodes.container('', paragraph)

    def _build_program_description(self, parser):
        """
        Build program description

        :param parser: pre-configured ArgumentParser instance
        :return: node forming program description
        """
        description = self._decorate_references(parser.description)
        description = description % dict(prog=parser.prog)
        result = nodes.container()
        self.state.nested_parse(StringList([description]), 0, result)
        return result

    def _build_program_options(self, parser, custom_content):
        """
        Build list of program options

        :param parser: pre-configured ArgumentParser instance
        :param custom_content: custom content for options
        :return: node forming program options
        """
        result = nodes.container()
        if self.ignore_option_groups:
            actions = parser._get_positional_actions() + parser._get_optional_actions()
            actions = [a for a in actions if a.help is not SUPPRESS]
            for action in actions:
                cc = [v for k, v in custom_content.items() if k in action.option_strings]
                result.append(self._build_option(parser, action, cc[0] if cc else None))
        else:
            for group in parser._action_groups:
                actions = [a for a in group._group_actions if a.help is not SUPPRESS]
                if actions:
                    title = nodes.title(text=group.title.capitalize())
                    options = nodes.container()
                    for action in actions:
                        cc = [v for k, v in custom_content.items() if k in action.option_strings]
                        options.append(self._build_option(parser, action, cc[0] if cc else None))
                    result.append(nodes.section('', title, options, ids=[group.title.lower()]))
        return result

    def _get_custom_content(self):
        """Load custom content for each section and for program options"""
        content = nodes.container()
        self.state.nested_parse(self.content, self.content_offset, content)
        sections = {}
        options = {}
        if len(content) and isinstance(content[0], nodes.definition_list):
            for item in content[0]:
                term = None
                classifiers = []
                definition = None
                for element in item.children:
                    if isinstance(element, nodes.term):
                        if element.children:
                            term = str(element[0]).lower()
                    elif isinstance(element, nodes.classifier):
                        if element.children:
                            classifiers.append(str(element[0]).lower())
                    elif isinstance(element, nodes.definition):
                        if element.children:
                            definition = nodes.container('', *element.children)
                if term in ['synopsis', 'description', 'options', 'option']:
                    action = [c[1:] for c in classifiers if c and c[0] == '@']
                    action = action[0] if action else 'append'
                    opts = [c for c in classifiers if c and c[0] != '@']
                    if definition:
                        if term != 'option':
                            sections[term] = dict(action=action, content=definition)
                        else:
                            for opt in opts:
                                options[opt] = dict(action=action, content=definition)
        return sections, options

    def _construct_main_sections(self, parser):
        """
        Construct Synopsis, Description and Options sections

        :param parser: pre-configured ArgumentParser instance
        :return: list of section nodes
        """
        cc_sections, cc_options = self._get_custom_content()
        result = []
        for section in ['synopsis', 'description', 'options']:
            method = '_build_program_{}'.format(section)
            method = getattr(self, method)
            args = [parser]
            if section == 'options':
                args.append(cc_options)
            title = nodes.title(text=section.upper())
            content = method(*args)
            if section in cc_sections:
                cc = cc_sections[section]
                if cc['action'] == 'append':
                    content.extend(cc['content'].children)
                elif cc['action'] == 'prepend':
                    content[0:0] = cc['content'].children
                elif cc['action'] == 'replace':
                    content[:] = cc['content']
            else:
                # append empty paragraph to ensure separation from consecutive section
                content.append(nodes.paragraph(text=''))
            result.append(nodes.section('', title, content, ids=[section.lower()]))
        return result

    def _get_parser(self):
        """Get parser instance"""
        function = self.options.get('function')
        module = self.options.get('module')
        # import module and get instance of function to call
        parts = function.split('.')
        try:
            mod = __import__(module, globals(), locals(), [parts[0]])
        except ImportError as e:
            raise AutoArgsError('Problem importing module: {}'.format(str(e)))
        try:
            obj = getattr(mod, parts[0])
            for sub in parts[1:]:
                obj = getattr(obj, sub)
        except AttributeError as e:
            raise AutoArgsError('Problem accessing function: {}'.format(str(e)))
        # instantiate object
        try:
            parser = obj()
        except TypeError as e:
            raise AutoArgsError('Problem calling function: {}'.format(str(e)))
        if not isinstance(parser, ArgumentParser):
            raise AutoArgsError('Function must return instance of argparse.ArgumentParser or derived class')
        return parser

    def run(self):
        """Run the directive"""
        parser = self._get_parser()
        parser.prog = self.options.get('program_name', parser.prog)
        env = self.state.document.settings.env
        env.ref_context['std:program'] = self._get_program_name(parser)
        self.synopsis_max_width = self.options.get('synopsis_max_width', 80)
        self.ignore_option_groups = 'ignore_option_groups' in self.options
        env.autoargs_options = dict(synopsis_max_width=self.synopsis_max_width,
                                    ignore_option_groups=self.ignore_option_groups)
        return self._construct_main_sections(parser)


def setup(app):
    app.add_directive('autoargs', AutoArgsDirective)
    return dict(version='0.1')
