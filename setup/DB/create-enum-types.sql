-- DLM enum definitions
CREATE TYPE location_type AS ENUM ('src', 'aws', 'gcs', 'low-operational', 'low-itf', 'mid-itf', 'dp', 'external');
CREATE TYPE location_country AS ENUM ('AU', 'ZA', 'UK');
CREATE TYPE config_type AS ENUM ('rclone', 'ssh', 'aws', 'gcs');
CREATE TYPE storage_type AS ENUM ('filesystem', 'objectstore', 'tape');
CREATE TYPE storage_interface AS ENUM ('posix', 's3', 'sftp', 'https');
CREATE TYPE phase_type AS ENUM ('GAS', 'LIQUID', 'SOLID', 'PLASMA');
CREATE TYPE item_state AS ENUM ('initialized', 'ready', 'corrupted', 'expired', 'deleted');
CREATE TYPE checksum_method AS ENUM (
  'none', 'adler32', 'blake2b', 'blake2s', 'crc32', 'crc32c', 'fletcher32', 'highwayhash', 'jenkinslookup3', 'md5', 'metrohash128',
  'sha1', 'sha224', 'sha256', 'sha384', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', 'sha512', 'shake_128', 'shake_256',
  'spookyhash', 'xxh3'
);
CREATE TYPE mime_type AS ENUM (
  'application/fits', 'application/gzip', 'application/json', 'application/mp4', 'application/msword',
  'application/octet-stream', 'application/pdf', 'application/postscript', 'application/rtf',
  'application/vnd.ms-cab-compressed', 'application/vnd.ms-excel', 'application/vnd.ms-powerpoint',
  'application/vnd.rar', 'application/vnd.sqlite3', 'application/x-7z-compressed', 'application/x-bzip',
  'application/x-bzip2', 'application/x-cpio', 'application/x-debian-package', 'application/x-gzip',
  'application/x-hdf', 'application/x-iso9660-image', 'application/x-ms-application', 'application/x-msdownload',
  'application/x-rar-compressed', 'application/x-sh', 'application/x-shellscript', 'application/x-tar',
  'application/x-tex', 'application/x-zip-compressed', 'application/xml', 'application/yaml', 'application/zip',
  'application/zip-compressed', 'audio/mp4', 'image/jpeg', 'image/png', 'image/tiff', 'text/csv', 'text/html',
  'text/javascript', 'text/markdown', 'text/plain', 'text/tab-separated-values', 'text/x-c', 'text/x-fortran',
  'text/x-java-source', 'text/x-python', 'video/mp4'
);