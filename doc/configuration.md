# Configuration

Program configuration is done with a configuration file. The file
location must be specified on the command line. Apart from the name of
the configuration file, an option **--no-gui** may be specified, to
prevent the popup of a summary message box when processing is complete.
Running the program without any arguments shows a quick usage popup
message. To ease specifying new configurations, a
[template file](../template.toml) is provided. The syntax is
[toml](https://github.com/toml-lang/toml), an ini-like language for use
in configuration files.

The configuration file has three main sections: [Server](#server),
[Project](#project), and [Local](#local).

## Server

This section specifies details of the server to retrieve the items from,
and how to retrieve them:

* **hostname**: the hostname (or IP address) of the server
* **port**: the server's port; this should be the web server port
* **user** and **password**: credentials to use to connect to the
  server; these will be sent in an `Authentication: Basic` HTTP header
* **https**: (true|false, default false): whether HTTPS is required to
   connect to the server
* **threads**: (1-20, default 1): the number of simultaneous requests to
   make to the server

If the server to connect to can't be reached on the internal web server
port, make sure that the _/api/atelier/v1_ URL is exposed; this is the
API used to retrieve the items.

Specifying a **threads** value higher than one can have a significant
impact on the speed of retrieving the items. The biggest gain is to be
expected on projects with a large number of items, residing on a server
on a not-too-fast network. The optimal number depends on both the server
the items are retrieved from, and the computer this program is running
on. A good first try could be the number of CPUs on the latter.
Specifying the maximum value is often slower than the optimal value, so
if speed is important, some experimentation may be required.

## Project

The program is based on the concept of a project, specifying which items
belong together and should be checked in in the same repository. This
allows having multiple projects (e.g., component libraries) in a single
namespace, handling them separately. Each project then has a separate
configuration file.

This section specifies the items that belong to the project. These may
include classes, mac-files, include files, CSP files, and some data
files: Ensemble _data lookup tables_ and _system default settings_.

The most important setting is **items**. It contains a list of
specifications stating what to include or, if preceded with a minus,
what to exclude. Lists are delimited with brackets: `[...]`. Wildcards
in the specifications are supported, using an asterisk. The type of item
to retrieve must be specified (except for CSP items, see below).
Supported item types are `cls`, `mac`, `int`, `inc`, `bas`, and `mvi`.

Some examples:

* `[ 'Strix.*.cls' ]` This list contains a single specification. It will
  retrieve all classes in package `Strix`, including subpackages.
* `[ 'Strix.*.cls', '-Strix.Tests.*.cls' ]` Includes all classes in
  package `Strix` and subpackages, except those in package `Strix.Test`
  (and subpackages).

Exclude specifications (those prefixed with a minus) are always
evaluated before include specifications; the order of the specifications
in the configuration file doesn't matter.

CSP items are specified by starting the specification with the CSP
application path, including leading forward slash:

* `[ '/csp/dev/*' ]` Includes all files under `/csp/dev`. This returns
  all file types, including images, CSS files, etc.
* `[ '/csp/dev/*.csp' ]` Includes all `*.csp` files under `/csp/dev`,
  excluding all other file types.

Additional configuration options in this section are:

* **mapped** (true|false, default false) specifies whether items mapped
  to the configured namespace from other databases should be included,
  if they match the item specs. This could be useful to include items in
  e.g. database _HSLOCAL_.
* **generated** (true|false, default false) specifies whether to include
  generated classes, if they match the item specs.
* **lookup** is a list of Ensemble _data lookup tables_ to retrieve, if any.
  These are saved in the configured data directory, with a `.lut` extension.
  (They may be specified with or without.) Wildcards are supported as with
  _items_ above.

## Project.enssettings

This subsection of [Project](#project) specifies if and how to retrieve the
Ensemble _system default settings_. The configuration options are:

* **name** should be either `Ens.Config.DefaultSettings.esd` (to retrieve
  them) or empty.
* **strip** (true|false, default false) specifies whether the actual
  values in the default settings should be stripped when retrieving
  them.

## Local

This section specifies what should be done with the downloaded items.

Directories specified here, which are not an absolute path, will be taken
relative to the location of the configuration file. In addition, the
literal string `{cfgname}` in a directory name will be replaced with the
name of the configuration file (without `.toml` extension). It is
convenient to give the configuration file the same name as the checkout
directory, and place it in the directory directly above it.

Note that if companion program
[iris-export-builder](https://github.com/gertjanklein/iris-export-builder)
is to be used, it is important to keep normal sources in separate
directories from CSP files and data items. The default settings do this.

Configuration options are:

* **dir** is the directory to save items to. Defaults to
  `{cfgname}\src`.
* **cspdir** is the directory to save CSP items to. Defaults to
  `{cfgname}\csp`. This should be placed outside the non-CSP items
  directory, so these can be loaded with e.g. `$System.OBJ.ImportDir()`.
* **datadir** is the directory to save data files to. Defaults to
  `{cfgname}\data`. Keep these separate as well.
* **logdir** is the directory for the log file. If empty, the log file
  is placed adjacent to the configuration file. It will always have
  the name of the config file, with ".toml" replaced with ".log".
* **encoding** specifies the encoding to use to save files in; it
  defaults to `UTF-8`, which is appropriate in most cases. For a list of
  possible alternatives, see
  [here](https://docs.python.org/3.7/library/codecs.html#standard-encodings).
* **subdirs** (true|false, default false) specifies whether items should
  be saved to subdirs per package, or all together in the source
  directory. If this is `true`, class `Strix.XML.Util` will be saved (by
  default) as `{cfgname}\src\Strix\XML\Util.cls`, otherwise as
  `{cfgname}\src\Strix.XML.Util.cls`.
* **cookies** (true|false, default false) specifies whether server
  cookies should be saved to file, so they can be reused between runs.
  This is mostly useful to reduce CSP license count usage on older
  systems. (CSP licenses are used as items are retrieved using a CSP
  API.)
* **disable_eol_fix** (true|false, default false) allows disabling a fix
  that saves the proper number of newlines when exporting CSP and
  routine items. Before version 0.4.7, one final newline was stripped.
  With this fix, exporting and re-importing does not change the file.
  Disabling this fix could be useful to prevent many whitespace-only
  changes in an existing repository.
