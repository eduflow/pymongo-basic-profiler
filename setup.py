import setuptools

setuptools.setup(
    name="pymongo-basic-profiler",
    version="0.0.1",
    url="https://github.com/peergradeio/pymongo-basic-profiler",
    author="Malthe Jørgensen",
    author_email="malthe@peergrade.io",
    description="A library that monkey-patches pymongo in order to count database queries",
    long_description=open('README.md').read(),
    packages=setuptools.find_packages(),
    install_requires=['pymongo'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
)
