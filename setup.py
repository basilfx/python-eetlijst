from setuptools import setup

# Setup definitions
setup(
    name="python-eetlijst",
    version="1.4.0",
    description="Unofficial Python API to interface with Eetlijst.nl",
    long_description=open("README.rst").read(),
    author="Bas Stottelaar",
    author_email="basstottelaar@gmail.com",
    py_modules=["eetlijst"],
    setup_requires=["nose"],
    install_requires=["requests", "beautifulsoup4", "pytz"],
    platforms=["any"],
    license="GPLv3",
    url="https://github.com/basilfx/python-eetlijst",
    keywords="python eetlijst api studenten studentenhuizen",
    test_suite="tests",
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: System :: Networking",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
    ],
)
