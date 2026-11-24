import importlib
import inspect

from docutils import nodes
from sphinx import addnodes
from sphinx.util.docutils import SphinxDirective

TAG_ASYNC = 'async'
TAG_FUNCTION = 'def'
BOX_CLASS = 'class-overview'
COLUMN_CLASS = 'class-overview-column'
REFERENCE_CLASSES = ['xref', 'py', 'py-meth']
CONSTRUCTOR = '__init__'


def import_class(class_path):
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)

    return getattr(module, class_name)


def constructor_parameters(cls):
    return list(inspect.signature(cls).parameters)


def public_methods(cls):
    return [
        (name, member) for name, member in vars(cls).items()
        if not name.startswith('_') and inspect.isfunction(member)
    ]


def method_tag(function):
    return TAG_ASYNC if inspect.iscoroutinefunction(function) else TAG_FUNCTION


def reference(class_path, member, text):
    literal = nodes.literal(text, text, classes=REFERENCE_CLASSES)

    return addnodes.pending_xref(
        '', literal, refdomain='py', reftype='meth',
        reftarget=f'{class_path}.{member}', refexplicit=True, refwarn=True
    )


def parameter_items(class_path, cls):
    return [[reference(class_path, CONSTRUCTOR, name)] for name in constructor_parameters(cls)]


def tag_literal(function):
    tag = method_tag(function)

    return nodes.literal(tag, tag)


def method_items(class_path, cls):
    return [
        [tag_literal(function), nodes.Text(' '), reference(class_path, name, name)]
        for name, function in public_methods(cls)
    ]


def bullet_list(items):
    return nodes.bullet_list('', *[nodes.list_item('', nodes.paragraph('', '', *item)) for item in items])


def column(title, items):
    return nodes.container('', nodes.rubric(title, title), bullet_list(items), classes=[COLUMN_CLASS])


class ClassOverview(SphinxDirective):
    required_arguments = 1

    def run(self):
        class_path = self.arguments[0]
        cls = import_class(class_path)

        columns = {
            'Parameters': parameter_items(class_path, cls),
            'Methods': method_items(class_path, cls),
        }

        populated = [column(title, items) for title, items in columns.items() if items]
        if not populated:
            raise self.error(f'{class_path} has no constructor parameters and no public methods')

        return [nodes.container('', *populated, classes=[BOX_CLASS])]


def setup(app):
    app.add_directive('classoverview', ClassOverview)

    return {'parallel_read_safe': True, 'parallel_write_safe': True}
