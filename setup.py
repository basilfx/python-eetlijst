from setuptools import setup

# Setup definitions
setup(
    name="python-eetlijst",
    version="1.3",
    description="Unofficial Python API to interface with Eetlijst.nl",
    author="Bas Stottelaar",
    author_email="basstottelaar@gmail.com",
    py_modules=["eetlijst"],
    install_requires=["requests", "beautifulsoup4", "python-dateutil", "pytz"],
    license = "GPLv3",
    keywords = "python eetlijst api studenten",
    test_suite="tests",
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: System :: Networking",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
    ],
)