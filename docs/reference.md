# API reference

The public building blocks of the protocol, generated from the docstrings. The command-line interface is described by `driftwatch --help` and each subcommand's `--help`.

## Time slicing and the constraints

```{eval-rst}
.. automodule:: driftwatch.data.slicer
   :members:
.. automodule:: driftwatch.data.constraints
   :members:
```

## Metrics

```{eval-rst}
.. automodule:: driftwatch.metrics.aut
   :members:
```

## Label delay and the sealed queue

```{eval-rst}
.. automodule:: driftwatch.sim.queue
   :members:
```

## Run configuration

```{eval-rst}
.. automodule:: driftwatch.sim.config
   :members: RunConfig, config_hash, lock_sha256, package_versions
```

## Detectors

```{eval-rst}
.. automodule:: driftwatch.models.base
   :members:
```

## Conformal layer

```{eval-rst}
.. automodule:: driftwatch.conformal.mondrian
   :members:
.. automodule:: driftwatch.conformal.nonconformity
   :members:
```

## Drift monitors

```{eval-rst}
.. automodule:: driftwatch.monitors.base
   :members:
```
