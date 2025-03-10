from setuptools import setup, find_packages

setup(
    name="mcp",
    version="0.5.0",
    package_dir={"": "."},
    packages=find_packages(where=".") + ["src"],
    package_data={"": ["*.json"]},
    install_requires=[
        "rich>=10.0.0",
        "python-dotenv>=0.19.0",
        "requests>=2.26.0",
        "pandas>=1.3.0",
        "python-telegram-bot>=20.0",
        "jpype1>=1.3.0",
        "py4j>=0.10.9.5",
    ],
    python_requires=">=3.8",
) 