from setuptools import setup

with open('README.md', 'r') as f:
    readme_str = f.read()

setup(
    name='spotify-lite',
    url='https://github.com/orangeblock/spotify-lite',
    author="orangeblock",
    author_email="noreply@void.dev",
    version='1.1.0',
    description='Lightweight, single-file, zero-dependency Spotify wrapper for Python 2.7+ and Python 3.x.',
    long_description=readme_str,
    long_description_content_type='text/markdown',
    license='MIT',
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    include_package_data=True,
    packages=['spotify']
)
