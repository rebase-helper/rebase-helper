SPECFILE_SECTIONS=['%header', # special "section" for the start of specfile
                   '%description',
                   '%package',
                   '%prep',
                   '%build',
                   '%install',
                   '%clean',
                   '%check',
                   '%files',
                   '%changelog']

TEMPLATE_DIR="rebasehelper_workspace"
RUNTIME_SECTIONS=['%prep', '%build', '%install', '%clean', '%check']
METAINFO_SECTIONS=['%header', '%package']
