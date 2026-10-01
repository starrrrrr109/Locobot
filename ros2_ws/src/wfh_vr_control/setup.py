from setuptools import find_packages, setup

package_name = 'wfh_vr_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'vrarm = wfh_vr_control.vrarm:main',
            'camera_fusion = wfh_vr_control.camera_fusion:main',
            'joy = wfh_vr_control.my_joy_control:main'
        ],
    },
)
