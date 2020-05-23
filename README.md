# copy-iris-items

Copies items from a remote Caché/IRIS server to a local directory.

## Motivation

Sometimes it is necessary to work with multiple programmers in a single
server namespace. To keep version history clean and accurate, it is
still desirable to have each programmer check in their own work. This
means that the server-side code maps to multiple (presumably local)
repositories.

In this specific situation, working with Atelier is error-prone, as it
assumes the filesystem is leading, not the server. If, e.g., developer 1
deletes a class, and later developer 2 starts Atelier and still has that
class in their repository, it will be uploaded to the server again. It
appears this behavior can't be turned off.

Studio doesn't have this problem, as/but it has no direct support for
synchronizing server-side code with a local repository. This program is
intended to fill that gap.

## Description

The tool syncs a local directory with a remote Caché/IRIS server. This
is done by downloading items specified in a configuration file. After
the files are downloaded, a local tool can be used to check the files
into source control.

When code one person is working on is ready to check in, they can:

* update their repository from e.g. GitHub
* run this program to get the latest code from the server
* check in and optionally push their code

(Note that this program does not in any way handle the repository or
checkin process. This is best left to specialized tools; for git/GitHub,
e.g. TortoiseGit or GitHub Desktop could be used.)

The program is most conveniently used as a drop target for the
configuration file. See template.toml for the possible configurations.

Items to download can be classes, macs, CSP files, etc. Items are saved
in UDL, not XML. Text items (that is, everything besides binary CSP
files) are, by default, encoded with UTF-8. If you already have a
repository where a different encoding is used, the configuration allows
you to override that.

In addition, Ensemble Data Lookup Tables and default configuration
settings can be downloaded.

The application is a Python (version 3.6+) script. In addition to the
Python standard library, it only uses the
[toml library](https://pypi.org/project/toml/).
It is known to work with Python 3.7, but other versions probably work as
well.

On the server side, the program uses part of the Atelier REST API that
is used for the same purpose by InterSystems Atelier. As a result, it
can only be used on servers that support that API, i.e. Caché 2016.2 or
later.

## Basic configuration

The program requires a configuration file to be specified on its command
line. It takes no other commandline arguments. For details of what can
be specified in the  configuration file, see file template.toml. The
syntax is [toml](https://github.com/toml-lang/toml), an ini-like
language for use in configuration files.

The configuration file has three main sections: Server, Project, and Local.

### Server

This section specifies details of the server to connect to (hostname or
IP address, port, credentials, namespace). The port to specify is the
web server port (the same one the management portal uses), not the
superserver port.

### Project

The program is based on the concept of a project, specifying which items
belong together and should be checked in in the same repository. This
allows having multiple projects (e.g., component libraries) in a single
namespace, handling them separately. This section specifies the items
that belong to the project. These may include classes, mac-files,
include files, CSP files. Ensemble data lookup tables are also
supported, and preliminary support for Ensemble default configuration
settings is present.

### Local

This section specifies what should be done with the downloaded files. It
specifies where to save source, CSP, and data files, and what encoding
to use (where appropriate).

## Usage

The program is a (non-console) python script. If you already have an
appropriate version of Python installed, you can just
[download it](https://github.com/gertjanklein/copy-iris-items/archive/master.zip),
`pip install toml`, and use the script directly:

```txt
copy-iris-items.pyw <project.toml>
```

If you don't have Python installed, or prefer an executable, you can
download a binary release for Windows
[here](https://github.com/gertjanklein/copy-iris-items/releases).
The program has no installer; just unzip it somewhere appropriate.

It is easiest to create a shortcut to the program (either script or
binary) next to the configuration file, and drag and drop it on the
shortcut when you want to run the program with it. Alternatively, a
batch/command file could be created that calls the program path+name
with the configuration filename as its single commandline argument. This
batch file can then be doubleclicked to start the synchronization.

When the program is done, a simple popup shows the number of items
that were synchronized. This may take a few seconds for large projects,
as each item has to be downloaded individually. Additionally, a log
file is maintained, and each synchronized item is listed there.

If an error occurs, a popup shows a simple description. The log file
usually has more details. Most likely errors are configuration file
syntax errors, wrong credentials, or connection errors.

By default, the log file is placed adjacent to the configuration
file, but a directory for it to be placed in may be configured.
It will have the same name as the configuration file.
