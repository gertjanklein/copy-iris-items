# copy-iris-items

Copies items from a remote Caché/IRIS server to a local directory.

Intended use is to sync a local directory (e.g. a git repository) with a
remote Caché/IRIS server. This is done by downloading items specified in
an INI file. After the files are downloaded, a local tool can be used to
check the files into source control.

The program is most conveniently used as a drop target for the INI file.
See template.ini for the possible configurations.

Items to download can be classes, macs, CSP files, etc. Items are saved
in UDL, not XML. Text items (that is, everything besides binary CSP
files) are, by default, encoded with UTF-8. If you already have a
repository where a different encoding is used, the .ini-file allows you
to override that.

The application is a Python (version 3.x) script. It only uses the
Python standard library. It is known to work with Python 3.7, but other
versions probably work as well.

On the server side, the program uses part of the Atelier REST API that
is used for the same purpose by InterSystems Atelier. As a result, it
can only be used on servers that support that API, i.e. Caché 2016.2 or
later.

## Usage

The program requires an .ini-file to be specified on its command line.
It takes no other commandline arguments. For details of what can be
specified in the .ini-file, see file template.ini.

The program is a (non-console) python script. If you already have an
appropriate version of Python installed, you can just
[download it](https://github.com/gertjanklein/copy-iris-items/archive/master.zip),
unzip, and use the script directly:

```txt
copy-iris-items.pyw <project.ini>
```

If you don't have Python installed, you can download a binary release
for Windows
[here](https://github.com/gertjanklein/copy-iris-items/releases).

It is easiest to create a shortcut to the program (either script or
binary) next to the .ini-file, and drag and drop the .ini-file on the
shortcut when you want to run the program with that .ini-file.
