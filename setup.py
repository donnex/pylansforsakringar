from distutils.core import setup

setup(
    name='pylansforsakringar',
    version='1.0.0',
    description='Lansforsakringar Python library (scraping)',
    py_modules=['lansforsakringar'],

    author='Daniel Johansson',
    author_email='donnex@donnex.net',
    license='BSD',

    install_requires=[
        'requests',
        'beautifulsoup4',
        'awesome-slugify',
    ]
)
