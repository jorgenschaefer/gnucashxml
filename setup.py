#!/usr/bin/env python

import shutil

from distutils.core import setup

shutil.copy("README.md", "README.txt")

setup(name='gnucashxml',
      version='1.0',
      description="Parse GNU Cash XML files",
      author="Jorgen Schaefer",
      author_email="forcer@forcix.cx",
      url="https://github.com/jorgenschaefer/gnucashxml",
      py_modules=['gnucashxml']
      )
