from setuptools import setup, find_packages

setup(
    name="kubetofu",
    version="1.0.0",
    description="Deep Agentic Infrastructure as Code CLI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Dwin Gharibi",
    author_email="team@kubetofu.io",
    url="https://github.com/dwin-gharibi/kubetofu",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.7.0",
        "httpx>=0.26.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "websockets>=12.0",
        "anthropic>=0.18.0",
        "openai>=1.10.0",
    ],
    entry_points={
        "console_scripts": [
            "kubetofu=kubetofu.main:app",
            "kt=kubetofu.main:app",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Build Tools",
    ],
    keywords="infrastructure terraform opentofu kubernetes ai agents arvancloud",
)
