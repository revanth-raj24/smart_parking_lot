-- Run once on your MySQL server before first launch
CREATE DATABASE IF NOT EXISTS smart_parking CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'parkinguser'@'localhost' IDENTIFIED BY 'changeme123';
GRANT ALL PRIVILEGES ON smart_parking.* TO 'parkinguser'@'localhost';
FLUSH PRIVILEGES;
