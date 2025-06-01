# Publishing a new version of the package

- Update the version number in setup.py
- Update the CHANGELOG
- git commit -m "vX.Y.Z"
- git tag vX.Y.Z
- make dist
- make upload
- git push
- git push --tag
