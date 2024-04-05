from setuptools import setup, find_packages

setup(
    name='singletscope',  # Name of your package
    version='0.1.0',  # Initial version of your package
    packages=find_packages(),  # Automatically find and include all packages
    install_requires=[
        'pyvisa',  # Dependency on PyVISA for instrument communication
        'matplotlib',  # Dependency on matplotlib for plotting
    ],
    author='Grisha Spektor',  # Your name or your organization's name
    author_email='grisha.spektor@gmail.com',  # Your email or your organization's email
    description='A Python package to control and acquire data from Siglent oscilloscopes',
    long_description=open('README.md').read(),  # Long description read from the the readme file
    long_description_content_type='text/markdown',  # Content type of the long description
    url='https://github.com/grishaspektor/singletscope',  # URL to the repository
    keywords=['oscilloscope', 'Siglent', 'instrumentation', 'data acquisition'],  # Keywords
    classifiers=[
        'Development Status :: 3 - Alpha',  # Development status
        'Intended Audience :: Developers',  # Target audience
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',  # License
        'Programming Language :: Python :: 3',  # Supported programming languages
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
)
