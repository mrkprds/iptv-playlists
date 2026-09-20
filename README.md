# iptv-playlists

One merged IPTV playlist built from [iptv-org/iptv](https://github.com/iptv-org/iptv)
plus [Harleythetech/IPHTV](https://github.com/Harleythetech/IPHTV) for the Philippines,
rebuilt weekly by a GitHub Action (Monday 02:00 Manila). Load this URL in UHF:

```
https://raw.githubusercontent.com/mrkprds/iptv-playlists/main/iptv-country-genre.m3u
```

Channels are grouped country first, genre within (`PH - News`, `UK - Sports`, ...).

To rebuild on demand, open the **Actions** tab and run **build-playlists** manually.
