

## Spack-freeze

a [Spack extension](https://spack.readthedocs.io/en/latest/extensions.html#custom-extensions) to generate a packages.yaml fragment listing a package and its dependencies as non-buildable externals.


### Usage

In most cases you can just do:

  spack freeze pkg@ver1 > freeze_pkg.yaml

You can then include freeze_package.yaml in an envrionment spack.yaml file
to use that package as a dependency.

    spack:
      include:
      - freeze_pkg.yaml
      specs: [pkg2@ver2 ^pkg@ver1]

### Installation

After cloning the repository somewhere, See the [Spack docs](https://spack.readthedocs.io/en/latest/extensions.html#configure-spack-to-use-extensions) on adding the path to config.yaml under 'extensions:'
