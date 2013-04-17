#!/usr/bin/env python

from setuptools import setup
import os

DESCRIPTION = open(
    os.path.join(os.path.dirname(__file__), 'README.md')).read().strip()

setup(
    name='chromedebug',
    version='0.1a0',
    description='A Chrome debugger protocol server for Python',
    author='Patryk Zawadzki',
    author_email='patrys@room-303.com',
    url='https://github.com/patrys/chromedebug',
    packages=['chromedebug', 'chromedebug.boot'],
    keywords=['debugger', 'chrome'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Debuggers',
        'Operating System :: OS Independent'],
    install_requires=['ws4py'],
    entry_points={
        'console_scripts': ['chromedebug = chromedebug:main']},
    long_description=DESCRIPTION)
