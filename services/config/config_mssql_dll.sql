
drop table CHEN_FILE_STYLES; 
drop table CHEN_FILE_UPLOADS_ARCHIVED;
drop table CHEN_FILE_UPLOADS_SHARED;
drop table CHEN_FILE_UPLOADS; 

CREATE TABLE CHEN_FILE_STYLES (
	OWNER char(30),
	SRC_FILE_PATH nvarchar(200),
	DRAWING_INFO TEXT,
	primary key (owner, src_file_path)
); 

CREATE TABLE CHEN_FILE_UPLOADS (
	OWNER char(30),
	SRC_FILE_PATH nvarchar(200),
	CACHE_FILE_PATH ntext,
	DATA_NAME char(100),
	DATA_SIZE integer,
	LAST_MODIFIED datetime NOT NULL,
	LAST_UPLOADED datetime NOT NULL,
	LAST_ACCESSED datetime NOT NULL, 
	UPLOAD_STATUS char(25) NOT NULL,
	TOTAL_ROW_COUNT integer NOT NULL,
	CACHED_ROW_COUNT integer NOT NULL, 
	--EMAIL char(100)
	primary key (owner, src_file_path)
);
  
CREATE TABLE CHEN_FILE_UPLOADS_ARCHIVED (	
	OWNER char(30),
	SRC_FILE_PATH nvarchar(200),
	CACHE_FILE_PATH ntext,
	DATA_NAME char(100),
	DATA_SIZE integer,
	LAST_MODIFIED datetime NOT NULL,
	LAST_UPLOADED datetime NOT NULL,
	LAST_ACCESSED datetime NOT NULL, 
	UPLOAD_STATUS char(25) NOT NULL,
	TOTAL_ROW_COUNT integer NOT NULL,
	CACHED_ROW_COUNT integer NOT NULL, 	
	ARCHIVED  datetime,  
	primary key (owner, src_file_path, archived)
);

CREATE TABLE CHEN_FILE_UPLOADS_SHARED (	
	OWNER char(30),
	SRC_FILE_PATH nvarchar(200),
	SHARED_USER char(30) NOT NULL,
	SHARED_DATE  datetime NOT NULL,  
	primary key (owner, src_file_path, shared_user), 
	foreign key (owner, src_file_path) references CHEN_FILE_UPLOADS(owner, src_file_path) on delete cascade
);
