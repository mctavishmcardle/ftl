from setuptools import setup

setup(
    name="ftl",
    version="0.0",
    py_modules=['ftl'],
    install_requires=['Click'],
    entry_points="""
        [console_scripts]
        ftl=ftl:cli
    """
)
