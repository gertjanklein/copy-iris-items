# copy-iris-items
Copy items from a remote Caché/IRIS server to a local directory.

Intended use it so keep a local directory (e.g. a git repository) in sync with
a remote server. This is done by downloading items specified in an INI file.
The program is most conveniently used as a drop target for the INI file. See
template.ini for the possible configurations.

Items to download can be classes, macs, CSP files, etc. Items are saved in UDL,
not XML. The encoding used is UTF-8, except for CSP items not recognised by
IRIS as text (and, obviously, binary files like images); these are saved as-is.

This application uses part of the Atelier API that is used for the same purpose
by InterSystems Atelier.

