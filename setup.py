import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="discoin",
    version="3.1.11",
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
    python_requires='>=3.6',
)