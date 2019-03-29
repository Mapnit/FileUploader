
drop table CHEN_FILE_STYLES; 
drop table CHEN_FILE_UPLOADS_ARCHIVED;
drop table CHEN_FILE_UPLOADS_SHARED;
drop table CHEN_FILE_UPLOADS; 

CREATE TABLE CHEN_FILE_STYLES (
	OWNER nvarchar(30),
	SRC_FILE_PATH nvarchar(200),
	DRAWING_INFO TEXT,
	primary key (owner, src_file_path)
); 

CREATE TABLE CHEN_FILE_UPLOADS (
	OWNER nvarchar(30),
	SRC_FILE_PATH nvarchar(200),
	CACHE_FILE_PATH ntext,
	DATA_NAME nvarchar(100),
	DATA_SIZE integer,
	LAST_MODIFIED datetime NOT NULL,
	LAST_UPLOADED datetime NOT NULL,
	LAST_ACCESSED datetime NOT NULL, 
	UPLOAD_STATUS nvarchar(25) NOT NULL,
	TOTAL_ROW_COUNT integer NOT NULL,
	CACHED_ROW_COUNT integer NOT NULL, 
	--EMAIL nvarchar(100)
	primary key (owner, src_file_path)
);
  
CREATE TABLE CHEN_FILE_UPLOADS_ARCHIVED (	
	OWNER nvarchar(30),
	SRC_FILE_PATH nvarchar(200),
	CACHE_FILE_PATH ntext,
	DATA_NAME nvarchar(100),
	DATA_SIZE integer,
	LAST_MODIFIED datetime NOT NULL,
	LAST_UPLOADED datetime NOT NULL,
	LAST_ACCESSED datetime NOT NULL, 
	UPLOAD_STATUS nvarchar(25) NOT NULL,
	TOTAL_ROW_COUNT integer NOT NULL,
	CACHED_ROW_COUNT integer NOT NULL, 	
	ARCHIVED  datetime,  
	primary key (owner, src_file_path, archived)
);

CREATE TABLE CHEN_FILE_UPLOADS_SHARED (	
	OWNER nvarchar(30),
	SRC_FILE_PATH nvarchar(200),
	SHARED_USER nvarchar(30) NOT NULL,
	SHARED_DATE  datetime NOT NULL,  
	primary key (owner, src_file_path, shared_user), 
	foreign key (owner, src_file_path) references CHEN_FILE_UPLOADS(owner, src_file_path) on delete cascade
);
