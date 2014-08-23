from distutils.core import setup
import os.path
import re


def get_version():
    path = os.path.join(os.path.dirname(__file__), 'huhhttp', '__init__.py')
    with open(path, 'r') as in_file:
        content = in_file.read()
    return re.search(r"__version__ = '([\w_.+-]+)'", content).group(1)


def main():
    setup(
        name='huhhttp',
        version=get_version(),
        description='An evil web server',
        author='Christopher Foo',
        author_email='chris.foo@gmail.com',
        url='https://github.com/chfoo/huhhttp',
        packages=['huhhttp', 'huhhttp.fusil'],
        package_data={'huhhttp': [
            'asset/*.?[a-zA-Z0-9]',
            'asset/*.??[a-zA-Z0-9]',
            'asset/images/*.?[a-zA-Z0-9]',
            'asset/images/*.??[a-zA-Z0-9]',
        ]},
        license='License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Topic :: Software Development :: Testing',
            'Topic :: Internet :: WWW/HTTP',
        ]
    )

if __name__ == '__main__':
    main()

