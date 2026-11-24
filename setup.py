import re
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("discoin/config.py", "r") as fh:
    version = re.search(r'^VERSION = "(.+)"$', fh.read(), re.MULTILINE).group(1)

setuptools.setup(
    name="discoin",
    version=version,
    author="Dr_Ari_Gami",
    author_email="drarigami@gmail.com",
    description="Official Discoin Package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Discoin/discoin.py",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=["aiohttp>=3.8"],
    python_requires='>=3.6',
)