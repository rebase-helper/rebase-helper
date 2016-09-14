import re

from docutils import nodes
from sphinx.writers.manpage import ManualPageTranslator
from sphinx.builders.manpage import ManualPageBuilder


class CustomManPageTranslator(ManualPageTranslator):
    """
    Manual page translator which properly formats option text roles
    and option directives
    """
    def __init__(self, builder, *args, **kwds):
        ManualPageTranslator.__init__(self, builder, *args, **kwds)
        self.option_context = []

    @staticmethod
    def _format_option(text):
        """
        Format single option, make option strings bold and option arguments italic
        """
        def get_font(token):
            # option strings start with "-"
            return 'B' if token['text'].startswith('-') else 'I'
        # find all tokens to be decorated, excluding "..."
        matches = list(re.finditer(r'[^\s\[\]{}=,|]+', text))
        tokens = [dict(text=m.group(0), span=m.span()) for m in matches if m.group(0) != '...']
        for t in reversed(tokens):
            text = text[: t['span'][1]] + '\\fP' + text[t['span'][1]:]
            text = text[: t['span'][0]] + '\\f{}'.format(get_font(t)) + text[t['span'][0]:]
        return text

    def visit_desc_signature(self, node):
        self.visit_definition_list_item(node)
        self.body.append('\n')

    def depart_desc_signature(self, node):
        # format option text formed by preceding desc_names and desc_addnames
        if self.option_context:
            self.body.append(self._format_option(''.join(self.option_context)))
            del self.option_context[:]
        self.body.append('\n')

    def visit_desc_name(self, node):
        # save text for later
        self.option_context.append(node.astext())
        raise nodes.SkipNode

    def visit_desc_addname(self, node):
        text = node.astext()
        # desc_addname node containing only "," is taken as option separator
        if text.strip() == ',':
            # format option text formed by preceding desc_names and desc_addnames
            if self.option_context:
                self.body.append(self._format_option(''.join(self.option_context)))
                del self.option_context[:]
        else:
            # save text for later
            self.option_context.append(text)
            raise nodes.SkipNode

    def visit_reference(self, node):
        if node.children and isinstance(node[0], nodes.literal):
            if 'std-option' in node[0].get('classes', ''):
                # prevent ignoring nested option node
                raise nodes.SkipDeparture
        ManualPageTranslator.visit_reference(self, node)

    def visit_literal(self, node):
        if 'std-option' in node.get('classes', ''):
            # format option text
            self.body.append(self._format_option(node.astext()))
            raise nodes.SkipNode
        else:
            self.visit_emphasis(node)

    def depart_literal(self, node):
        self.depart_emphasis(node)

    def visit_manpage(self, node):
        text = node.astext()
        # parentheses and section numbers inside them shouldn't be bold
        text = re.sub(r'(\(\d*\))', r'\\fR\1\\fP', text)
        self.body.append('\\fB{}\\fP'.format(text))
        raise nodes.SkipNode


class CustomManPageBuilder(ManualPageBuilder):
    """Manual page builder which uses CustomManualPageTranslator"""
    name = 'custom-man'

    def init(self):
        ManualPageBuilder.init(self)
        # use custom translator
        self.translator_class = CustomManPageTranslator


def setup(app):
    app.add_builder(CustomManPageBuilder)
    return dict(version='0.1')
