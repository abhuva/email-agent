from setuptools import setup, find_packages

setup(
    name='email-agent',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'pyyaml',
        'python-dotenv',
    ],
    extras_require={
        'dev': ['pytest'],
    },
)
