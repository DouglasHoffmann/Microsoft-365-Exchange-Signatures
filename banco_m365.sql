

CREATE DATABASE [Microsoft365]
 CONTAINMENT = NONE
 ON  PRIMARY 
( NAME = N'Microsoft365', FILENAME = N'D:\BancoDeDados\Microsoft365.mdf' , SIZE = 8192KB , MAXSIZE = UNLIMITED, FILEGROWTH = 65536KB )
 LOG ON 
( NAME = N'Microsoft365_log', FILENAME = N'D:\LogBD\Microsoft365_log.ldf' , SIZE = 8192KB , MAXSIZE = 2048GB , FILEGROWTH = 65536KB )
 WITH CATALOG_COLLATION = DATABASE_DEFAULT, LEDGER = OFF
GO


CREATE TABLE [dbo].[signatures](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[user_email] [nvarchar](255) NOT NULL,
	[full_name] [nvarchar](255) NOT NULL,
	[job_title] [nvarchar](255) NULL,
	[phone_number] [nvarchar](50) NULL,
	[department] [nvarchar](255) NULL,
	[signature_html] [nvarchar](max) NULL,
	[created_at] [datetime] NULL,
	[updated_at] [datetime] NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[user_email] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

ALTER TABLE [dbo].[signatures] ADD  DEFAULT (getdate()) FOR [created_at]
GO

ALTER TABLE [dbo].[signatures] ADD  DEFAULT (getdate()) FOR [updated_at]
GO




CREATE PROCEDURE [dbo].[upsert_signature]
    @user_email NVARCHAR(255),
    @full_name NVARCHAR(255),
    @job_title NVARCHAR(255) = NULL,
    @phone_number NVARCHAR(50) = NULL,
    @department NVARCHAR(255) = NULL,
    @signature_html NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    MERGE INTO signatures AS target
    USING (SELECT @user_email AS user_email) AS source
    ON target.user_email = source.user_email
    WHEN MATCHED THEN
        UPDATE SET 
            full_name = @full_name, 
            job_title = @job_title, 
            phone_number = @phone_number, 
            department = @department, 
            signature_html = @signature_html, 
            updated_at = GETDATE()
    WHEN NOT MATCHED THEN
        INSERT (user_email, full_name, job_title, phone_number, department, signature_html, created_at, updated_at)
        VALUES (@user_email, @full_name, @job_title, @phone_number, @department, @signature_html, GETDATE(), GETDATE());
END;
GO

CREATE PROCEDURE [dbo].[get_all_signatures]
AS
BEGIN
    SET NOCOUNT ON;

    SELECT user_email, full_name, job_title, phone_number, department, signature_html
    FROM signatures;
END;
GO


CREATE PROCEDURE [dbo].[delete_signature]
    @user_email NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM signatures WHERE user_email = @user_email;
END;
GO


CREATE PROCEDURE [dbo].[get_signature]
    @user_email NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT user_email, full_name, job_title, phone_number, department, signature_html
    FROM signatures
    WHERE LOWER(LTRIM(RTRIM(user_email))) = LOWER(LTRIM(RTRIM(@user_email)));
END;
GO

