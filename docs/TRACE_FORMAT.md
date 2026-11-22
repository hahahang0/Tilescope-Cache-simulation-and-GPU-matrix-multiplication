# Optional text trace format

The `cache_sim --trace PATH` option reads one operation and one byte address per line:

```text
R 0x00000000
W 0x00000040
R 128
```

`R` is a load and `W` is a store. Addresses may be decimal or use the `0x` hexadecimal prefix. The simulator applies write-back and write-allocate to both operations. Matrix mode does not materialize traces: it computes each address and feeds it directly into the cache model.
