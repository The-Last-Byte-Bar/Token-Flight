from setuptools import setup, find_packages

setup(
    name="ergonaut-airdrop",
    version="0.5.0",
    description="A comprehensive airdrop and token distribution tool for the Ergo blockchain",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Ergonaut Community",
    url="https://github.com/ergonaut-airdrop/ergonaut-airdrop",
    package_dir={"": "."},
    packages=find_packages(where=".") + ["src"],
    package_data={
        "": ["*.json", "*.env*"],
        "src": ["art/*", "ui/*"]
    },
    install_requires=[
        "rich>=10.0.0",
        "python-dotenv>=0.19.0",
        "requests>=2.26.0",
        "pandas>=1.3.0",
        "python-telegram-bot>=20.0",
        "jpype1>=1.3.0",
        "py4j>=0.10.9.5",
        "fleet-sdk>=0.1.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "console_scripts": [
            "ergonaut-airdrop=src.airdrop:main",
        ],
    },
) 