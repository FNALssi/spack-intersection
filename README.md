

## Spack-intersection

a [Spack extension](https://spack.readthedocs.io/en/latest/extensions.html#custom-extensions) to generate an  environment spack.yaml files from others, containing unlisted, shared, dependencies


### Usage

In most cases you can just do:

  spack intersection e1_spack.yaml e2_spack.yaml e3_spack.yaml

It will generate an "intersection_spack.yaml" file which you can
use to create overlapping environments, as:

```
spack env create int_env e1_spack.yaml
spack -e int_env concretize 
spack env create --include-concrete int_env e1 e1_spack.yaml
spack env create --include-concrete int_env e2 e2_spack.yaml
spack env create --include-concrete int_env e3 e3_spack.yaml
```
and those environments should share dependencies.
