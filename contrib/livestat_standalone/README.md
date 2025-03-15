# HTTP updates endpoint as a single executable

Written in Golang, striving for a single executable deploy. This is written as a testimonial to how terribly unfit Cloud is for inherently tiny use cases like these.

## Configuration

Set environment variables:

- `LISTEN` (optional) \
  `host:port` pair to listen at. Specified in golang `net/http` syntax. Default value `:38083`.
- `MASTER_TOKEN` (optional) \
  Token used to authenticate and authorize service creation, deletion, and updates.
- `DATA_FILE` (optional) \
  When specified, attempt to load state on startup, and save on every change to services.
  When unspecified. the entire state resides in memory only.

## Deploy

Run `go build` to generate the executable. Configure environment variables as needed. Run the executable.
You probably also wants to setup a reverse proxy like Nginx or Caddy to handle HTTPS termination.

Example:
```sh
export LISTEN=':8080'
export MASTER_TOKEN=hunter2
export DATA_FILE=data.json
./livestat_standalone
```

## Design Considerations

To keep it simple, every service resides in memory at all times. This should scale well up to tens of thousands of services, given enough memory.
The entire state file is overwritten on every change. This scale work well up to hundreds of services, but beyond that there may occur thrashing of disk.

Both of these scalability issues can be easily mitigated by using SQLite. The limit then becomes service update frequency (roughly tens of thousands per second), and disk size (however big your attached storage is).
SQLite is not used here because it's an extra dependency, and we're small enough there is just no point.
