drop table CHEN_FILE_UPLOADS_OLD; 

CREATE TABLE CHEN_FILE_UPLOADS_OLD (
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT NOT NULL,
	BOOKMARK_NAME char(100),
	DRAWING_INFO TEXT,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOAD DATE,
	UPLOAD_STATUS char(100),
	primary key (owner, src_file_path)
);

-- 7/15/2015 add the archive table to store the archived uploads rather than delete them

drop table CHEN_FILE_UPLOADS_OLD2; 

CREATE TABLE CHEN_FILE_UPLOADS_OLD2 (
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT NOT NULL,
	data_name char(100),
	DRAWING_INFO TEXT,
	DATA_SIZE integer,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOADED DATE NOT NULL,
	LAST_ACCESSED DATE NOT NULL, 
	UPLOAD_STATUS char(25),
	primary key (owner, src_file_path)
);
  

drop table CHEN_FILE_UPLOADS_ARCHIVED_OLD2;

CREATE TABLE CHEN_FILE_UPLOADS_ARCHIVED_OLD2 (	
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT NOT NULL,
	data_name char(100),
	DRAWING_INFO TEXT,
	DATA_SIZE integer,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOADED DATE NOT NULL,
	LAST_ACCESSED DATE NOT NULL, 
	UPLOAD_STATUS char(25),
	ARCHIVED  DATE,  
	primary key (owner, src_file_path, archived)
);

-- 7/28/2015 move the drawing_info column into a separate table for reuse through archiving

drop table CHEN_FILE_STYLES_OLD3; 

CREATE TABLE CHEN_FILE_STYLES_OLD3 (
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	DRAWING_INFO TEXT,
	primary key (owner, src_file_path)
); 

drop table CHEN_FILE_UPLOADS_OLD3; 

CREATE TABLE CHEN_FILE_UPLOADS_OLD3 (
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT NOT NULL,
	data_name char(100),
	DATA_SIZE integer,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOADED DATE NOT NULL,
	LAST_ACCESSED DATE NOT NULL, 
	UPLOAD_STATUS char(25),
	primary key (owner, src_file_path)
);
  
drop table CHEN_FILE_UPLOADS_ARCHIVED_OLD3;

CREATE TABLE CHEN_FILE_UPLOADS_ARCHIVED_OLD3 (	
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT NOT NULL,
	data_name char(100),
	DATA_SIZE integer,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOADED DATE NOT NULL,
	LAST_ACCESSED DATE NOT NULL, 
	UPLOAD_STATUS char(25),
	ARCHIVED  DATE,  
	primary key (owner, src_file_path, archived)
);

-- 8/4/2015 remove NOT NULL from CACHE_FILE_PATH to enable "PROCESSING" as a upload status
--			add NOT NULL to UPLOAD_STATUS
--			allow partial process (limit the number of rows)
--			add email as a column for notification (TODO)

drop table CHEN_FILE_STYLES; 

CREATE TABLE CHEN_FILE_STYLES (
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	DRAWING_INFO TEXT,
	primary key (owner, src_file_path)
); 

drop table CHEN_FILE_UPLOADS; 

CREATE TABLE CHEN_FILE_UPLOADS (
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT,
	DATA_NAME char(100),
	DATA_SIZE integer,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOADED DATE NOT NULL,
	LAST_ACCESSED DATE NOT NULL, 
	UPLOAD_STATUS char(25) NOT NULL,
	TOTAL_ROW_COUNT integer NOT NULL,
	CACHED_ROW_COUNT integer NOT NULL, 
	--EMAIL char(100)
	primary key (owner, src_file_path)
);
  
drop table CHEN_FILE_UPLOADS_ARCHIVED;

CREATE TABLE CHEN_FILE_UPLOADS_ARCHIVED (	
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	CACHE_FILE_PATH TEXT,
	DATA_NAME char(100),
	DATA_SIZE integer,
	LAST_MODIFIED DATE NOT NULL,
	LAST_UPLOADED DATE NOT NULL,
	LAST_ACCESSED DATE NOT NULL, 
	UPLOAD_STATUS char(25) NOT NULL,
	TOTAL_ROW_COUNT integer NOT NULL,
	CACHED_ROW_COUNT integer NOT NULL, 	
	ARCHIVED  DATE,  
	primary key (owner, src_file_path, archived)
);

-- 1/13/2016 add CHEN_FILE_UPLOADS_SHARED to support the file sharing between users
--			 note: the shared files would be read-only for data as well as style
--				   one file can't be shared with the same user more than once

drop table CHEN_FILE_UPLOADS_SHARED;

CREATE TABLE CHEN_FILE_UPLOADS_SHARED (	
	OWNER char(30),
	SRC_FILE_PATH TEXT,
	SHARED_USER char(30) NOT NULL,
	SHARED_DATE  DATE NOT NULL,  
	primary key (owner, src_file_path, shared_user), 
	foreign key (owner, src_file_path) references CHEN_FILE_UPLOADS(owner, src_file_path) on delete cascade
);

