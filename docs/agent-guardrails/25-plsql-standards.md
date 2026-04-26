# CoE Best Practice PLSQL

Naming conventions, commenting code, error handling and instrumentation

-   [1. Introduction](#CoEBestPracticePLSQL-Introduction)

-   [2. General Guidelines](#CoEBestPracticePLSQL-GeneralGuidelines)

    -   [2.1. Modular Code](#CoEBestPracticePLSQL-ModularCode)

    -   [2.2. Formatting](#CoEBestPracticePLSQL-Formatting)

-   [3. Variable Naming
    Conventions](#CoEBestPracticePLSQL-VariableNamingConv)

-   [4. Comments](#CoEBestPracticePLSQL-Comments)

    -   [4.1. Package Level
        Comments](#CoEBestPracticePLSQL-PackageLevelCommen)

    -   [4.2. Procedure / Function Level
        comments](#CoEBestPracticePLSQL-Procedure/Function)

    -   [4.3. Ace Extension](#CoEBestPracticePLSQL-AceExtension)

-   [5. Code](#CoEBestPracticePLSQL-Code)

    -   [5.1. Constants](#CoEBestPracticePLSQL-Constants)

    -   [5.2. Variables & Types](#CoEBestPracticePLSQL-Variables&Types)

    -   [5.3. Numeric Data
        Types](#CoEBestPracticePLSQL-NumericDataTypes)

-   [6. Control Structure
    Cursor](#CoEBestPracticePLSQL-ControlStructureCu)

    -   [6.1. CASE / IF / DECODE / NVL / NVL2 /
        COALESCE](#CoEBestPracticePLSQL-CASE/IF/DECODE/NVL)

    -   [6.2. Flow Control](#CoEBestPracticePLSQL-FlowControl)

-   [7. Exception Handling](#CoEBestPracticePLSQL-ExceptionHandling)

-   [8. Dynamic SQL](#CoEBestPracticePLSQL-DynamicSQL)

-   [9. Stored Objects](#CoEBestPracticePLSQL-StoredObjects)

    -   [9.1. Packages](#CoEBestPracticePLSQL-Packages)

-   [10. Best Practices](#CoEBestPracticePLSQL-BestPractices)

-   [11. Instrumentation](#CoEBestPracticePLSQL-Instrumentation)

    -   [11.1. Use of logger](#CoEBestPracticePLSQL-Useoflogger)

        -   [11.1.1. General
            Guidelines](#CoEBestPracticePLSQL-GeneralGuidelines.)

        -   [11.1.2. Example
            Pattern](#CoEBestPracticePLSQL-ExamplePattern)

        -   [11.1.3. Why This
            Matters](#CoEBestPracticePLSQL-WhyThisMatters)

        -   [11.1.4. ✅ Do and ❌ Don't Checklist for
            logger](#CoEBestPracticePLSQL-✅Doand❌Don’tCheckl)

# 1. Introduction

Please apply these coding standards when developing.  Standards bring
numerous benefits including

-   Well formatted code is easier to read, analyze and maintain

-   Ensures consistency making it easier to implement a team development
    environment.

-   Code has a structure and is uncluttered, such that it makes it
    easier to avoid making errors and also makes it easier to read.  

These standards should be relaxed in certain cases if they compromise
readability/support of code.

Please remember, that when maintaining code, you should strive to leave
code, looking better than how you found it.

# 2. General Guidelines

-   Comment your code! 

-   Always use meaningful and specific names.

-   Avoid using abbreviations unless the full name is excessively long.

-   Do not use Oracle reserved words as names. A list of Oracle's
    reserved words may be found in the dictionary view
    V\$RESERVED_WORDS.

-   Avoid adding redundant or meaningless prefixes and suffixes to
    identifiers. (e.g. emp_table).

-   Write all names in lowercase.

-   Defaulted function/procedure parameter(s) should be last in
    parameter list.

-   Identifier names (variables, procedure names, functions etc.) should
    not exceed 30 characters in length.

-   Try to limit the length of code lines. In general you should aim for
    80 characters. If necessary for trailing code comments (following
    code) this can be extended to 100.

**Example of Trailing Comments**

\-- Archiving one of the projects created

agr_api.prj_project_tapi.upd (

p_prj_project_id =\> g_project_arr(1)

, p_project_name =\> \'Archived Project\'

, p_description =\> \'none\'

, p_owner_id =\> \'bb\'

, p_archived_on =\> current_timestamp \-- we can archive them by simply

\-- specifying an archived_on timestamp

\-- and the arhived_by user name

, p_archived_by =\> \'bb\'

, p_last_modified_on =\> current_timestamp

, p_row_version =\> l_num

## 2.1. Modular Code

Avoid code which presents as over-complicated. Break the problem down
into digestible chunks, if necessary, create functions or procedures,
within the function or procedure you are working on. If there are
reusable bits of code, make them subroutines in their own right.  Not
only should this make it easier for someone to read your code, but it
will make your life easier for you, since a big problem, is made into a
number of smaller, more easily managed tasks.

## 2.2. Formatting

-   Always written in lowercase.

-   3 space indention. NO TABS!

-   One command per line.

-   Keywords else, elsif on a new line.

-   Commas at the beginning of separated elements including SQL.

-   Call parameters aligned, operators aligned, values aligned.

-   SQL keywords are right aligned within a SQL command.

-   Single, empty lines.

-   Leave a blank line between the end of one subroutine and the start
    of another.

It is especially important to avoid hard tabs. Any decent editor has an
option which allows soft tabs to be set.

**Basic IF statement Example**

if l_total \> lc_max

then

   l_new_max := true;

elsif l_total = lc_max

then

  l_new_max := false;

end if;

**PLSQL Code Example (without comments)** Expand source

create or replace package example_pkg as

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--   

 

gc_default_guid constant section.section_guid%type := \'default\';

 

procedure set_section_guid(

 p_code in section.section_code%type

,p_guid in section.section_guid%type default gc_default_guid

);

 

end example_pkg;

/

 

create or replace package body example_pkg as

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

   procedure set_section_guid(

    p_code in section.section_code%type

   ,p_guid in section.section_guid%type default gc_default_guid

   )

   is

 

      cursor cur_section (

       cp_code in section.section_code%type

      )

      is

      select section_pk

        from section

       where section_code = cp_code;

 

      l_section_pk section.section_pk%type;

 

      e_guid_is_invalid exception;

 

      pragma exception_init(ex_guid_is_invalid, -20125);

 

   begin

      if regexp_substr(p_guid,\'\[\[:alnum:\]\]\') is null then

         raise e_guid_is_invalid;

      end if; 

 

      \<\<lp_sections\>\>

      for rec_section in cur_section(

           cp_code =\> p_code

          )

      loop

         begin

            select section_pk

              into l_section_pk

              from sections scn

             where section_guid = rec_section.section_guid;

 

            update sections

               set section_guid = p_guid

             where section_pk   = rec_section.section_pk;

   

         exception

            when no_data_found

            then

               null;

         end;

      end loop lp_sections;

 

   exception

      when others then         

         afw_ilog.add_param (l_params, \'p_code\',  p_code);

         afw_ilog.add_param (l_params, \'p_guid \', p_guid);

         afw_error_handler.handle_exception (p_params =\> l_params);

         raise;

   end set_section_guid;

 

end example_pkg;

/

# 3. Variable Naming Conventions

When adding content to your code apply the following naming conventions

+------------------------------+-------------------+------------------+
| **Identifier**               | **Prefix**        | **Example**      |
+==============================+===================+==================+
| Global variable              | g                 | g_version        |
+------------------------------+-------------------+------------------+
| Local variable               | l                 | l_version        |
+------------------------------+-------------------+------------------+
| Cursor                       | cu                | cur_version      |
|                              | r                 |                  |
+------------------------------+-------------------+------------------+
| Cursor parameter             | cp                | cp_empno         |
+------------------------------+-------------------+------------------+
| Loop Labels                  | lp                | \<\              |
|                              |                   | <lp_sections\>\> |
+------------------------------+-------------------+------------------+
| Record Type                  | r                 | r_employee       |
+------------------------------+-------------------+------------------+
| Array / PL/SQL Table Type    | t                 | t_employee       |
+------------------------------+-------------------+------------------+
| Object                       | o                 | o_employee       |
+------------------------------+-------------------+------------------+
| Function / procedure         | p                 | p_text           |
| parameter                    |                   |                  |
+------------------------------+-------------------+------------------+
| Type definitions             | ty                | ty_employee      |
+------------------------------+-------------------+------------------+
| Exception                    | e                 | e                |
|                              |                   | _employee_exists |
+------------------------------+-------------------+------------------+
|                              |                   |                  |
+------------------------------+-------------------+------------------+
| Constants                    | gc = global       | gc_empno         |
|                              | constant          |                  |
|                              |                   | c_empno          |
|                              | c = local         |                  |
|                              | constant          |                  |
+------------------------------+-------------------+------------------+

# 4. Comments

Commenting code is important. It helps to convey what the code is meant
to achieve. Furthermore, it should help the coder to be clear, what
he/she is trying to achieve.  

There is another reason why comments are important. If you work on the
basis that the code itself, is self-documenting, then in the case of
code containing bugs, your documentation is wrong! Thus documenting the
code, may help someone to identify existing problems within the code.

Arguably, comments within the code, should be the most reliable source
of documentation, for a module. This is because it is less likely to be
out of date. Remember that when you modify code, you should ensure that,
where required, existing comments are altered to reflect the changes.
For non trivial enhancements, new comments should also be added. If you
are working on a problem, involving complicated, non-commented code, as
your work through the code, try to add comments to add clarity.

If you are making changes to code alter the comments to reflect the
logic.  If the existing comments can be improved on please enhance as
required.

Don\'t describe the code, describe what the code is trying to achieve
e.g. \"Loop to process rows from Cursor X\" is not a good comment,
\"Check each row from Cursor X validating the data, recording an error
when invalid or inserting the data when valid\".

The package, procedure and function level comments described below will
eventually form part of a formal self documenting mechanism.  A
corporate PL/SQL documentation protocol is being built that produces
documentation in the style of the public Oracle Product Documentation

## 4.1. Package Level Comments

The Ace Extension provides Liquibase snippets which in turn provide
standard package body and spec.  When the Ace snippets are not available
the same notation can be added manually.  We should use these to help
denote the purpose of the packaged logic in addition to in logic
comments.  This notation should be updated manually 

**Example lb-package-body-changeset snippet** Expand source

\--changeset ORACLE_GUID_TOKEN:PACKAGE_NAME_TOKEN_create_body
stripComments:false endDelimiter:/ runOnChange:true

create or replace package body SCHEMA_NAME_TOKEN.PACKAGE_NAME_TOKEN

as

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\--

\-- Copyright(C) 2024, Oracle Corporation

\-- All Rights Reserved

\--

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\-- Application : APPLICATION_TOKEN

\-- Sub-module : SUBMODULE_TOKEN

\-- Source file name : development_properties.sql

\-- Purpose : PURPOSE_TOKEN

\--

\-- Notes :

\-- NOTES_TOKEN

\--

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

We should initialize the following values

-   Application = This should reflect our project component e.g. AGR
    Agriculture, GVT Government or DGP Digital Government

-   Sub-Module = Should reflect the functional area e.g. Domain Lists or
    Project and Actions

-   Purpose = This is the most critical element and should be used to
    describe the content, purpose and use cases the package aims to
    achieve.

-   Notes = This section can cover the individual versions.  Add your
    GUID and the Jira Ticket number and date for each change and a short
    description of the change being applied

See <https://gbuconfluence.oraclecorp.com/x/rlfdJQ> for the agriculture
tech design which shows the Application and Sub modules

**Example package comment with changes across time** Expand source

\--changeset chrthoms:PACKAGE_NAME_TOKEN_create_body stripComments:false
endDelimiter:/ runOnChange:true

create or replace package body SCHEMA_NAME_TOKEN.PACKAGE_NAME_TOKEN

as

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\--

\-- Copyright(C) 2024, Oracle Corporation

\-- All Rights Reserved

\--

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\-- Application : DGP Digital Government

\-- Sub-module :   Helpers

\-- Source file name :   ENCRYPTION_UTIL.sql

\-- Purpose :   This package contains some useful functions allowing you

\-- to encrypt (or decrypt) / hash text values.

\-- These functions should be used when storing / retrieving

\-- sensitive data.

\--

\-- Notes :

\-- chrthoms 03 May 2024 DGGIU-1234 create first instance of package

\-- chrthoms 15 Aug 2024 DGGIU-4567 add HASH function to hash a given
string

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

## 4.2. Procedure / Function Level comments

Using a similar notation we can document each procedure or function

**Example package comment with changes across time** Expand source

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\-- Procedure : BASE64_DECODE

\-- Purpose :   Given a raw value that has been base64 encoded, this
function will return the decoded value as a varchar

\-- Parameters :   name = p_raw direction = in datatype = raw

\-- Syntax :   afw_encryption_util.base64_decode ( p_raw in raw );

\--

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\-- Example 1

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\-- set serveroutput on

\--

\-- declare

\-- l_base64_raw raw(64) :=
utl_raw.cast_to_raw(\'U1RSSU5HIFRPIEJBU0U2NCBERUNPREU=\');

\-- l_b64_decoded varchar2(1000);

\-- begin

\-- l_b64_decoded := afw_encryption_util.base64_decode ( p_raw =\>
l_base64_raw );

\-- dbms_output.put_line (\'BASE 64 Decoded Value: \' \|\|
l_b64_decoded);

\-- end;

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

## 4.3.  Ace Extension

There is an Ace Extension which provides some default AI driven comments
to your code.  You can use this extension to initialize the comments. 
Always comment to describe the logic, the AI generated comments give you
a start.

To apply the comments select the code you want to comment e.g. a
procedure in VS Code then select the ace extension \"ACE: Add AI
Comments (SQL)\" from the Command Palette action in the View menu.

+----------------------------------+-----------------------------------+
| **Procedure before Ace           | **Procedure after Ace             |
| Comments** Expand source         | Comments** Expand source          |
|                                  |                                   |
| procedure upd (                  | procedure upd (                   |
|                                  |                                   |
| p_gov_region_id in               | p_gov_region_id in                |
| gov_region.gov_region_id%type    | gov_region.gov_region_id%type,    |
|                                  |                                   |
| , p_region_name in               | p_region_name in                  |
| gov_region.region_name%type      | gov_region.region_name%type,      |
|                                  |                                   |
| , p_hierarchy_position in        | p_hierarchy_position in           |
| go                               | go                                |
| v_region.hierarchy_position%type | v_region.hierarchy_position%type, |
|                                  |                                   |
| , p_parent_gov_region_id in      | p_parent_gov_region_id in         |
| gov_                             | gov_                              |
| region.parent_gov_region_id%type | region.parent_gov_region_id%type, |
|                                  |                                   |
| , p_area in gov_region.area%type | p_area in gov_region.area%type,   |
|                                  |                                   |
| , p_region_geometry in           | p_region_geometry in              |
| gov_region.region_geometry%type  | gov_region.region_geometry%type,  |
|                                  |                                   |
| , p_bounding_box_geometry in     | p_bounding_box_geometry in        |
| gov_r                            | gov_r                             |
| egion.bounding_box_geometry%type | egion.bounding_box_geometry%type, |
|                                  |                                   |
| , p_centroid_geometry in         | p_centroid_geometry in            |
| g                                | g                                 |
| ov_region.centroid_geometry%type | ov_region.centroid_geometry%type, |
|                                  |                                   |
| , p_population in                | p_population in                   |
| gov_region.population%type       | gov_region.population%type,       |
|                                  |                                   |
| , p_population_density in        | p_population_density in           |
| go                               | go                                |
| v_region.population_density%type | v_region.population_density%type, |
|                                  |                                   |
| , p_row_version out              | p_row_version out                 |
| gov_region.row_version%type      | gov_region.row_version%type       |
|                                  |                                   |
| ) is                             | ) is                              |
|                                  |                                   |
| begin                            | begin                             |
|                                  |                                   |
| update gov_region                | \-- Update a single row in the    |
|                                  | gov_region table based on the     |
| set region_name =                | provided ID                       |
| upper(p_region_name)             |                                   |
|                                  | \-- and update the corresponding  |
| , hierarchy_position =           | columns with the new values       |
| p_hierarchy_position             |                                   |
|                                  | update gov_region                 |
| , parent_gov_region_id =         |                                   |
| p_parent_gov_region_id           | \-- Convert the region name to    |
|                                  | uppercase to ensure consistency   |
| , area = p_area                  |                                   |
|                                  | set region_name =                 |
| , region_geometry =              | upper(p_region_name)              |
| p_region_geometry                |                                   |
|                                  | , hierarchy_position =            |
| , bounding_box_geometry =        | p_hierarchy_position              |
| p_bounding_box_geometry          |                                   |
|                                  | , parent_gov_region_id =          |
| , centroid_geometry =            | p_parent_gov_region_id            |
| p_centroid_geometry              |                                   |
|                                  | , area = p_area                   |
| , population = p_population      |                                   |
|                                  | , region_geometry =               |
| , population_density =           | p_region_geometry                 |
| p_population_density             |                                   |
|                                  | , bounding_box_geometry =         |
| where gov_region_id =            | p_bounding_box_geometry           |
| p_gov_region_id                  |                                   |
|                                  | , centroid_geometry =             |
| returning row_version            | p_centroid_geometry               |
|                                  |                                   |
| into p_row_version;              | , population = p_population       |
|                                  |                                   |
|                                  | , population_density =            |
|                                  | p_population_density              |
|                                  |                                   |
|                                  | \-- Filter the update to only     |
|                                  | affect the row with the matching  |
|                                  | ID                                |
|                                  |                                   |
|                                  | where gov_region_id =             |
|                                  | p_gov_region_id                   |
|                                  |                                   |
|                                  | \-- Return the updated row        |
|                                  | version to the caller             |
|                                  |                                   |
|                                  | returning row_version             |
|                                  |                                   |
|                                  | into p_row_version;               |
|                                  |                                   |
|                                  | end upd;                          |
+==================================+===================================+
+----------------------------------+-----------------------------------+

# 5. Code

## 5.1. Constants

Avoid using literals in the main body of code. Instead declare these as
constants.

This carefully as to how the constant is to be used, before deciding
where it whould be declared. If it is to be used only within a single
procedure or function, then declare it there. If it is referenced at
various points within the package (more than one procedure / function),
declare it as a packge level variable, within the package body.  There
will be cases where the constant needs to be referenced across packages,
in which case, the constant needs to be declared in the package
specification.

**Example of a cross package reference** Expand source

create or replace package hr_actions

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

\--

\-- Author: \<author\>

\-- Script name:  hr_actions.sql (spec)

\-- Date: 21 Oct 2024

\-- Purpose: \<Implements\...\>

\--

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--

as

   c_opration_transfer constant varchar2(4000) := \'TRANSFER\';

   c_opration_fire     constant varchar2(4000) := \'FIRE\';

 

   procedure employee_action (

     p_action        in varchar2

   , p_empno         in emp.empno%type

   , p_target_depno  in emp.deptno%type

   );

 

end hr_actions;

/

create or replace package body hr_actions

as

 

   procedure employee_action (

     p_action        in varchar2

   , p_empno         in emp.empno%type

   , p_target_depno  in emp.deptno%type

   )

   is

   begin

 

      case p_action

      when c_opration_transfer

      then

         \-- business logic here

         null;

      when c_opration_fire

      then

         \-- business logic here

         null;

      else

         \-- business logic here

         null;

      end case;

 

   end employee_action;

 

end hr_actions;

/

**Referencing the constant in an API call** Expand source

begin

   hr_actions.employee_action (

     p_action        =\> hr_actions.c_opration_transfer

   , p_empno         =\> 1234

   , p_target_depno  =\> 20

   );

end;

## 5.2. Variables & Types

+---------------------------------+------------------------------------+
| **Convention**                  | **Reasoning**                      |
+=================================+====================================+
| Use anchored declarations for   | Explicit type declarations may     |
| variables, constants & types    | lead to errors if underlying       |
| where possible                  | database objects change.           |
|                                 |                                    |
|                                 | Example: l_ename  emp.ename%type;  |
+---------------------------------+------------------------------------+
| Define types in a single        | Single point of reference.         |
| location (type specification    |                                    |
| package)                        | Example:                           |
|                                 |                                    |
|                                 | l_c                                |
|                                 | ode_section  types_pkg.ty_ora_name |
|                                 | := 'TEST_PCK';                     |
+---------------------------------+------------------------------------+
| Avoid comparisons with null     |                                    |
| value.  Use IS \[NOT\] NULL.    |                                    |
+---------------------------------+------------------------------------+
| Avoid using overly short names  | The name chosen should define      |
| for declared or implicitly      | purpose and usage to be easily     |
| declared identifiers.           | understood.                        |
+---------------------------------+------------------------------------+

## 5.3. Numeric Data Types

+-----------------------------+----------------------------------------+
| **Convention**              | **Reasoning**                          |
+=============================+========================================+
| Include precision when      | Having precision undefined will use    |
| declaring NUMBER variables  | the default precision.  This level of  |
| or subtypes.                | precision may be unnecessary and       |
|                             | precision should be specified to match |
|                             | needs.                                 |
+-----------------------------+----------------------------------------+
| Try using PLS_INTEGER       | PLS_INTEGER uses less memory.          |
| instead of NUMBER for       |                                        |
| arithmetic operations with  | PLS_INTEGER uses machine arithmetic,   |
| integer values (no decimal  | which is up to three times faster than |
| point).                     | library arithmetic which is used by    |
|                             | NUMBER.                                |
+-----------------------------+----------------------------------------+

# 6. Control Structure Cursor

  ------------------------------------------------------------------------
  **Convention**              **Reasoning**
  --------------------------- --------------------------------------------
  Always                      Readability of code.
  use **%notfound** instead   
  of **not %found** to check  
  whether a cursor was        
  successful                  

  Always close locally opened Any cursors left open can consume additional
  cursors                     system global area memory space with the
                              database instance, potentially in both the
                              shared and private SQL pools.
  ------------------------------------------------------------------------

## 6.1. CASE / IF / DECODE / NVL / NVL2 / COALESCE

  ----------------------------------------------------------------------------
  Convention                 Reasoning
  -------------------------- -------------------------------------------------
  Try to use **case** rather **if** statements containing
  than an **if** statement   multiple **elsif** tend to become complex
  with                       quickly.
  multiple **elsif** paths   

  Try to use **case** rather **decode** is an older function that has been
  than **decode**            replaced by the easier to understand and more
                             common **case **function,

  Use **coalesce** instead   The NVL function always evaluates both parameters
  of **nvl**, if parameter 2 before deciding which one to use.  This can be
  of the **nvl **function is unnecessary if parameter 2 is either a function
  a function call or         call or a select statement, as it will be
  a **select** statement     executed regardless or whether parameter 1
                             contains a NULL value or not.

  Use **case** instead       The NVL2 function always evaluates all parameters
  of **nvl2** if parameter 2 before deciding which one to use.  This can be
  or 3 of **nvl2** is either unnecessary, if parameter 2 or 3 is either a
  a function case or a       function call or a select statement, as they will
  select statement           be executed regardless of whether parameter 1
                             contains a NULL value or not.
  ----------------------------------------------------------------------------

## 6.2. Flow Control

+-------------------------------------------+--------------------------+
| **Convention**                            | **Reasoning**            |
+===========================================+==========================+
| Avoid GOTO statements in your code        | Increases complexity and |
|                                           | maintenance of the code. |
+-------------------------------------------+--------------------------+
| Use label loops to increase readability   | **Example**              |
| (not mandatory).\                         |                          |
| Advisable for longer loop constructs.     | \<\<                     |
|                                           | lp_process_employees\>\> |
|                                           |                          |
|                                           | f                        |
|                                           | or rec_employee in (sele |
|                                           | ct empno, name from emp) |
|                                           |                          |
|                                           | loop                     |
|                                           |                          |
|                                           |   \...                   |
|                                           |                          |
|                                           | end loop                 |
|                                           | lp_process_employees;    |
+-------------------------------------------+--------------------------+
| Use a CURSOR FOR loop to process the      | **Example**              |
| complete cursor results unless you are    |                          |
| using bulk operations                     | \<\<                     |
|                                           | lp_process_employees\>\> |
|                                           |                          |
|                                           | for rec_                 |
|                                           | employee IN cur_employee |
|                                           |                          |
|                                           | loop                     |
|                                           |                          |
|                                           |   \...                   |
|                                           |                          |
|                                           | end loop                 |
|                                           | lp_process_employees;    |
+-------------------------------------------+--------------------------+
| Use a NUMERIC FOR loop to process a dense | **Example**              |
| array                                     |                          |
|                                           | \<\<                     |
|                                           | lp_process_employees\>\> |
|                                           |                          |
|                                           | for i IN t_employees.fir |
|                                           | st()..t_employees.last() |
|                                           |                          |
|                                           | loop                     |
|                                           |                          |
|                                           |   \...                   |
|                                           |                          |
|                                           | end loop                 |
|                                           | lp_process_employees;    |
+-------------------------------------------+--------------------------+
| Use a WHILE loop to process a loose array | **Example**              |
|                                           |                          |
|                                           | \<\<                     |
|                                           | lp_process_employees\>\> |
|                                           |                          |
|                                           | while                    |
|                                           | l_index is not null      |
|                                           |                          |
|                                           | loop                     |
|                                           |                          |
|                                           |   \...                   |
|                                           |                          |
|                                           |   l_index :=             |
|                                           | t_                       |
|                                           | employees.next(l_index); |
|                                           |                          |
|                                           | end loop                 |
|                                           | lp_process_employees;    |
+-------------------------------------------+--------------------------+
| Use EXIT WHEN instead of an IF statement  | **Example**              |
| to exit from a loop                       |                          |
|                                           | \<\<                     |
|                                           | lp_process_employees\>\> |
|                                           |                          |
|                                           | loop                     |
|                                           |                          |
|                                           |   \...                   |
|                                           |                          |
|                                           |   exit                   |
|                                           | lp_proces                |
|                                           | s_employees when (\...); |
|                                           |                          |
|                                           | end loop                 |
|                                           | lp_process_employees;    |
+-------------------------------------------+--------------------------+

# 7. Exception Handling

Coming Soon! \.....  More examples of exception handling 

+-----------------+----------------------------------------------------+
| **Convention**  | **Reasoning**                                      |
+=================+====================================================+
| Never handle    | **Example**                                        |
| unnamed         |                                                    |
| exceptions      | declare                                            |
| using the ORA   |                                                    |
| error number    |   ex_employee_exists  exception;                   |
|                 |                                                    |
|                 |   pragma exception_init (-1, e_employee_exists);   |
|                 |                                                    |
|                 |   \...                                             |
|                 |                                                    |
|                 | begin                                              |
|                 |                                                    |
|                 |   \...                                             |
|                 |                                                    |
|                 | exception                                          |
|                 |                                                    |
|                 |   when e_employee_exists                           |
|                 |                                                    |
|                 |   then                                             |
|                 |                                                    |
|                 |     \...                                           |
|                 |                                                    |
|                 | end;                                               |
+-----------------+----------------------------------------------------+
| Never assign    | The local declaration overrides the global         |
| predefined      | declaration which causes confusion. Prefixing      |
| exception names | exception names with \"e\_\", as prescribed by the |
| to user defined | standards, should eliminate the possibility of     |
| exceptions      | this happening.                                    |
+-----------------+----------------------------------------------------+
| Avoid using     | Assess whether it would be better to declare and   |
| Oracle's        | raise a project specific exception.                |
| predefined      |                                                    |
| exceptions      | Being as specific as possible with the errors      |
|                 | raised will allow developers to check for, and     |
|                 | handle, the different kinds of errors the code     |
|                 | might produce.                                     |
+-----------------+----------------------------------------------------+
| Use specific    | Separate exceptions should be raised for each      |
| exceptions for  | error condition, rather than re-using the same     |
| each case       | exception for different circumstances.             |
|                 |                                                    |
|                 | Being as specific as possible with the errors      |
|                 | raised will allow developers to check for, and     |
|                 | handle, the different kinds of errors the code     |
|                 | might produce.                                     |
+-----------------+----------------------------------------------------+

# 8. Dynamic SQL

+----------------+-----------------------------------------------------+
| **Convention** | **Reasoning**                                       |
+================+=====================================================+
| Use output     | When a dynamic INSERT, UPDATE or DELETE statement   |
| bind arguments | has a RETURNING clause, output bind arguments can   |
| in the         | go in the RETURNING INTO clause or in the USING     |
| returning into | clause.  Use the RETURNING INTO clause for values   |
| clause of      | returned from a DML operation.  Reserve OUT and IN  |
| dynamic        | OUT bind variables for dynamic PL/SQL blocks that   |
| insert, update | return values in PL/SQL variables.                  |
| or delete      |                                                     |
| statements     | **Example**                                         |
|                |                                                     |
|                | execute immediate sql_stmt using l_sal, l_empno     |
|                | returning into l_ename, l_job;                      |
+----------------+-----------------------------------------------------+

# 9. Stored Objects

+-----------------------+----------------------------------------------+
| **Convention**        | **Reasoning**                                |
+=======================+==============================================+
| Use named notation    | Named notation makes sure that changes to    |
| when calling program  | the signature of the called program unit do  |
| units                 | not affect the call.                         |
|                       |                                              |
|                       | **Example**                                  |
|                       |                                              |
|                       | rec_emp := employee_rec  ( p_empno    =\>    |
|                       | l_empno                                      |
|                       |                                              |
|                       |                          , p_ename_in =\>    |
|                       | l_ename );                                   |
+-----------------------+----------------------------------------------+
| Add the name of the   | **Example**                                  |
| program unit to its   |                                              |
| end keyword           | procedure set_salary                         |
|                       |                                              |
|                       | is                                           |
|                       |                                              |
|                       | begin                                        |
|                       |                                              |
|                       |   \...                                       |
|                       |                                              |
|                       | end set_salary;                              |
+-----------------------+----------------------------------------------+

## 9.1. Packages

  -----------------------------------------------------------------------
  **Convention**               **Reasoning**
  ---------------------------- ------------------------------------------
  Keep packages to a common    Readability, ease of support.
  sense size.  Include only    
  related procedures and       
  functions that are used in   
  the same context             

  The package header comments  Placing the header comments before the
  should not precede the line  \"create or replace package
  containing \"create or       \<package_name\>\", creates a line offset,
  replace package              which makes it less straight forward to
  \<package_name\>\".          locate lines subject to compilation error.
  -----------------------------------------------------------------------

# 10. Best Practices

  -----------------------------------------------------------------------
  **Convention**                     **Reasoning**
  ---------------------------------- ------------------------------------
  While using SELECT \... INTO,      Exception handling.
  handle all exceptions especially,  
  no_data_found and too_many_rows.   
  Or use for loop to handle above    
  mentioned scenarios.               

  When retrieving a single record,   SELECT \... INTO will always raise
  use SELECT \... INTO rather than a an exception when the query returns
  cursor OPEN, FETCH, CLOSE (or      no data or too many rows. With the
  cursor FOR loop).                  cursor method it is too easy to miss
                                     this and cause a bug.

  Use ANSI joins rather than \"comma More readable and makes it easier to
  joins\" in SQL.                    spot missing join predicates.

  Avoid exposing global variables in Global variable values should be
  package specs                      defined in the package body so that
                                     only the package\'s own code can
                                     change them.

  Enable compiler warnings           Compiler warnings can point out
                                     unwanted code, such as unused
                                     program units and global variables
                                     defined in the package spec.
  -----------------------------------------------------------------------

# 11. Instrumentation

## 11.1. Use of logger

All PL/SQL packages in the Food Security project (including TAPIs,
XAPIs, and supporting packages) must adopt consistent use of the
[[logger]{.underline}](https://github.com/OraOpenSource/Logger)
framework for observability and diagnostics. This provides structured,
parameterised trace output that is invaluable during debugging, system
monitoring, and test execution.

### 11.1.1. General Guidelines

-   **Always declare a scope constant**\
    Each package should declare a gc_unit_prefix constant, based on
    \$\$PLS_UNIT. This ensures all log entries can be traced back to the
    owning unit.

-   gc_unit_prefix constant varchar2(64) := lower(\$\$pls_unit) \|\|
    \'.\';

-   **Use a scope variable per procedure**\
    Inside each public (and significant private) procedure or function,
    define an l_scope variable, derived from gc_unit_prefix plus the
    subprogram name.

-   l_scope logger_user.logger_logs.scope%type := gc_unit_prefix \|\|
    \'ins\';

-   **Capture parameters**\
    Use logger_user.logger.append_param for relevant input values.

    -   Prefix key parameters with \* (e.g. \* p_id) to highlight
        identifiers.

    -   Avoid logging large or sensitive values (e.g. CLOBs, passwords).

> l_params logger_user.logger.tab_param;
>
> logger_user.logger.append_param(l_params, \'\* p_test_id\',
> p_test_id);
>
> logger_user.logger.append_param(l_params, \' p_project_code\',
> p_project_code);

-   **Log start and end of each subprogram**\
    Place a logger.log(\'START\', \...) call before main logic, and a
    matching logger.log(\'END\', \...) before normal exit.

> logger.log(\'START\', l_scope, null, l_params);
>
> \...
>
> logger.log(\'END\', l_scope);

-   Log exceptions consistently\
    Catch when others then, log the error with the same l_scope and
    l_params, then re-raise to ensure proper error propagation.

>  
>
> exception when others then
>
> logger_user.logger.log_error(\'Unhandled exception\', l_scope, null,
> l_params);
>
> raise;

### 11.1.2. Example Pattern

procedure ins (

p_test_id in dqu_pluggable_binds.test_id%type,

p_bind_name in dqu_pluggable_binds.bind_name%type,

p_row in out dqu_pluggable_binds%rowtype

) is

l_scope logger_user.logger_logs.scope%type := gc_unit_prefix \|\|
\'ins\';

l_params logger_user.logger.tab_param;

begin

\-- Record key inputs

logger_user.logger.append_param(l_params, \'\* p_test_id\', p_test_id);

logger_user.logger.append_param(l_params, \'\* p_bind_name\',
p_bind_name);

\-- Entry

logger.log(\'START\', l_scope, null, l_params);

\-- Main logic

insert into dqu_pluggable_binds (test_id, bind_name, project_code)

values (p_test_id, p_bind_name, p_row.project_code)

returning row_version into p_row.row_version;

\-- Exit

logger.log(\'END\', l_scope);

exception

when others then

logger_user.logger.log_error(\'Unhandled exception\', l_scope, null,
l_params);

raise;

end ins;

### 11.1.3. Why This Matters

-   Provides **traceability** across all APIs (table-level or
    cross-table).

-   Ensures **uniform logging structure**, making it easier to filter
    and search logs.

-   Aids **diagnostics during test runs** (e.g. with utPLSQL) without
    polluting production logic.

-   Protects against "silent failures" by always logging before
    re-raising exceptions.

### 11.1.4. ✅ Do and ❌ Don't Checklist for logger

**✅ Do:**

-   Declare a gc_unit_prefix constant once per package.

-   Use a local l_scope for each subprogram.

-   Log **START** and **END** consistently.

-   Capture **key identifiers** with \* (e.g. \* p_id).

-   Include contextual params needed to diagnose failures.

-   Log exceptions with log_error before re-raising.

-   Keep log messages **short, structured, and searchable**.

**❌ Don't:**

-   ❌ Log sensitive information (passwords, tokens, personally
    identifiable data).

-   ❌ Dump entire CLOB/BLOBs --- they flood logs and slow queries.

-   ❌ Forget to close out with an **END** entry --- incomplete traces
    confuse debugging.

-   ❌ Mix inconsistent scope strings --- always use gc_unit_prefix \|\|
    subprogram.

-   ❌ Swallow exceptions after logging --- always re-raise.

-   ❌ Over-log trivial steps (noise dilutes the useful signal).
