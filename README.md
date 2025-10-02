# le-homelab
me n mi homelab addiction &lt;3

Mi Mini Router (128 MB):
  DNS router for local services
  Simple websites

4th-gen i5 (16 GB) — “Media & Apps”, 2 fast hard drives, connects with the VPS

  Sharing a hard drive:
  
    Jellyfin (use Intel Quick Sync for transcoding)
  
    Navidrome (music-only server is tiny; perfect here)
    
    Calibre-Web (UI only) pointing at books synced in
  
  CVAT (isolate from media IO if you can: separate disk/dataset or at least separate mount) - separate drive for now

  Management UI and small web servers: SMART data, statistics, etc, can live on boot drive

  Other small docker images

3rd-gen i5 (8 GB) — “Ingest & Storage”, 1 fast 1 slow, Periodic syncing with 4th gen

  Sharing the fast drive:
  
    qBittorrent + Radarr (behind Surfshark/WireGuard)
    
    YouTube audio/movies downloader (yt-dlp FastAPI/Go)
    
    Readarr + Calibre (book pipeline), telegram downloader

  Backup + SAMBA server for file sharing: slow drive

  Other small lightweight docker images, management scripts to communicate issues with 4th gen scripts
  
  
