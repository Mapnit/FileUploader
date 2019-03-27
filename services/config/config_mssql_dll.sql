DROP TABLE [CHEN_FILE_UPLOADS_SHARED]; 

CREATE TABLE [CHEN_FILE_UPLOADS_SHARED] (	
	OWNER char(30),
	SRC_FILE_PATH NVARCHAR (200),
	SHARED_USER char(30) NOT NULL,
	SHARED_DATE  DATE NOT NULL,  
	primary key (owner, src_file_path, shared_user), 
	foreign key (owner, src_file_path) references [CHEN_FILE_UPLOADS](owner, src_file_path) on delete cascade
);

DROP TABLE [CHEN_FILE_UPLOADS]; 

CREATE TABLE [CHEN_FILE_UPLOADS] (
    [OWNER]            CHAR (30)      NOT NULL,
    [SRC_FILE_PATH]    NVARCHAR (200) NOT NULL,
    [CACHE_FILE_PATH]  NTEXT		  NULL,
    [DATA_NAME]        CHAR (100)     NULL,
    [DATA_SIZE]        INT            NULL,
    [LAST_MODIFIED]    DATE           NOT NULL,
    [LAST_UPLOADED]    DATE           NOT NULL,
    [LAST_ACCESSED]    DATE           NOT NULL,
    [UPLOAD_STATUS]    CHAR (25)      NOT NULL,
    [TOTAL_ROW_COUNT]  INT            NOT NULL,
    [CACHED_ROW_COUNT] INT            NOT NULL,
    PRIMARY KEY CLUSTERED ([OWNER] ASC, [SRC_FILE_PATH] ASC)
);

DROP TABLE [CHEN_FILE_UPLOADS_ARCHIVED];

CREATE TABLE [CHEN_FILE_UPLOADS_ARCHIVED] (
    [OWNER]            CHAR (30)      NOT NULL,
    [SRC_FILE_PATH]    NVARCHAR (200) NOT NULL,
    [CACHE_FILE_PATH]  NTEXT		  NULL,
    [DATA_NAME]        CHAR (100)     NULL,
    [DATA_SIZE]        INT            NULL,
    [LAST_MODIFIED]    DATE           NOT NULL,
    [LAST_UPLOADED]    DATE           NOT NULL,
    [LAST_ACCESSED]    DATE           NOT NULL,
    [UPLOAD_STATUS]    CHAR (25)      NOT NULL,
    [TOTAL_ROW_COUNT]  INT            NOT NULL,
    [CACHED_ROW_COUNT] INT            NOT NULL,
    [ARCHIVED]         DATE           NOT NULL,
    PRIMARY KEY CLUSTERED ([OWNER] ASC, [SRC_FILE_PATH] ASC, [ARCHIVED] ASC)
);


DROP TABLE [CHEN_FILE_STYLES]; 

CREATE TABLE [CHEN_FILE_STYLES] (
	OWNER char(30),
	SRC_FILE_PATH NVARCHAR (200),
	DRAWING_INFO NTEXT,
	primary key (owner, src_file_path)
); 

