from setuptools import setup, find_namespace_packages

with open('README.md', encoding='utf8') as f:
    long_description = f.read()

setup(
    name="pyGPT",
    version="0.1.0",
    description="An unofficial API allowing free interaction with ChatGPT in Python",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license="GNU General Public License v2.0",
    packages=find_namespace_packages("src"),
    package_dir={"": "src"},
    install_requires=["tls-client>=0.2.2"],
    author="Alfred Tonic",
    keywords=["chatgpt", "openai"],
    url="https://github.com/alfred-exe/pyGPT"
)
