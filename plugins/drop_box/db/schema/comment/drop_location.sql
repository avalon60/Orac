--liquibase formatted sql

--changeset clive:drop_box_comment_drop_location context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
comment on table orac_dropbox.drop_location is 'Configured filesystem locations scanned by the drop-box ingestion plugin.'
;
comment on column orac_dropbox.drop_location.processing_instruction is 'Instruction snapshot source copied to each job at enqueue time.'
;
