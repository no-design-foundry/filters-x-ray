from setuptools import setup, find_packages

setup(
    name='x_ray',
    version='0.2.1',
    packages=find_packages(),
    description='no design foundry – x-ray plugin',
    author='Jan Sindler',
    author_email='jansindl3r@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    keywords='x-ray, ndf, plugin',
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'ndf_x_ray=x_ray.x_ray:main',
        ],
    },
)