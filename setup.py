from setuptools import setup, find_packages

setup(
    name='ratel',
    version='0.0.1',
    packages=find_packages(),
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "ratel = ratel.main:main",
        ]
    },

    author='timchow',
    author_email='744475502@qq.com',
    url='http://timd.cn/',
    description='A Python asynchronous network library',
    keywords='asynchronous network',
    license='MIT')

