--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_validation_api_body context:plugin,prod labels:plugin stripComments:false runOnChange:true runAlways:true endDelimiter:/
create or replace package body orac_chess.chess_validation_api as
  function pgn_header(p_pgn clob,p_name varchar2) return varchar2 is
  begin
    validate_pgn(p_pgn,false);
    begin
      return chess_mle_header(p_pgn,p_name);
    exception
      when others then
        raise_application_error(-20020,'Chess validation runtime is unavailable.');
    end;
  end;
  procedure lock_control is
    l_id number;
  begin
    select control_id into l_id from chess_admin_control where control_id=1 for update;
  end;
  procedure require_version(p_actual number, p_expected number) is
  begin
    if p_expected is null or p_actual != p_expected
    then
      raise_application_error(-20001, 'This record changed. Reload before saving.');
    end if;
  end;
  procedure validate_url(p_url varchar2) is
  begin
    if p_url is not null and (not regexp_like(p_url, '^https?://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]+)?(/|\?|#|$)', 'i')
       or regexp_like(p_url, '[[:cntrl:]<>" ]') or instr(p_url, chr(92)) > 0)
    then
      raise_application_error(-20002, 'Use a valid HTTP or HTTPS URL.');
    end if;
  end;
  procedure validate_opening(p_id number, p_parent_id number) is
    l_count number;
  begin
    if p_parent_id is not null
    then
      select count(*) into l_count from chess_opening where opening_id=p_parent_id;
      if l_count=0
      then
        raise_application_error(-20003, 'Parent opening does not exist.');
      end if;
      select count(*) into l_count from (
        select opening_id from chess_opening
        start with opening_id=p_parent_id
        connect by nocycle prior parent_opening_id=opening_id
      ) where opening_id=p_id;
      if l_count>0
      then
        raise_application_error(-20004, 'An opening cannot contain a hierarchy cycle.');
      end if;
    end if;
  end;
  procedure validate_pgn(p_pgn clob, p_single_line boolean, p_fen varchar2 default null) is
    l_error varchar2(700);
    l_single number := case when p_single_line then 1 else 0 end;
  begin
    -- SQL CLOB lengths are characters; the JS policy also bounds UTF-16 length.
    if p_pgn is null or dbms_lob.getlength(p_pgn) not between 1 and 4194304
    then
      raise_application_error(-20021,'PGN must contain 1 to 4194304 characters.');
    end if;
    begin
      l_error := chess_mle_validate(p_pgn,l_single,p_fen);
    exception
      when others then
        raise_application_error(-20020,'Chess validation runtime is unavailable.');
    end;
    if l_error is not null
    then
      raise_application_error(-20021,l_error);
    end if;
  end validate_pgn;
  procedure validate_branch(p_parent clob,p_child clob,p_ply number,p_fen varchar2) is
    l_error varchar2(700);
  begin
    validate_pgn(p_parent,true,p_fen);
    validate_pgn(p_child,true,p_fen);
    begin
      l_error := chess_mle_branch(p_parent,p_child,p_ply,p_fen);
    exception
      when others then
        raise_application_error(-20020,'Chess validation runtime is unavailable.');
    end;
    if l_error is not null
    then
      raise_application_error(-20025,l_error);
    end if;
  end validate_branch;
  procedure validate_variation_tree(p_id number) is
    type visited_type is table of boolean index by varchar2(40);
    l_visited visited_type;
    l_root chess_variation%rowtype;
    l_node chess_variation%rowtype;
    l_parent chess_variation%rowtype;
    l_id number := p_id;
  begin
    -- The caller's singleton lock protects the complete aggregate until commit.
    lock_control;
    loop
      if l_visited.exists(to_char(l_id))
      then
        raise_application_error(-20024,'A variation cannot contain a hierarchy cycle.');
      end if;
      l_visited(to_char(l_id)) := true;
      select * into l_node from chess_variation where variation_id=l_id;
      exit when l_node.parent_variation_id is null;
      l_id := l_node.parent_variation_id;
    end loop;
    l_root := l_node;
    validate_pgn(l_root.pgn,true,l_root.starting_fen);
    for node in (
      select variation_id,connect_by_iscycle cycle_found
      from chess_variation
      start with variation_id=l_root.variation_id
      connect by nocycle prior variation_id=parent_variation_id
    ) loop
      if node.cycle_found=1
      then
        raise_application_error(-20024,'A variation cannot contain a hierarchy cycle.');
      end if;
      select * into l_node from chess_variation where variation_id=node.variation_id;
      if nvl(l_node.opening_id,-1)<>nvl(l_root.opening_id,-1)
         or nvl(l_node.gambit_id,-1)<>nvl(l_root.gambit_id,-1)
      then
        raise_application_error(-20022,'Every variation in a tree must have the same owner.');
      end if;
      if l_node.parent_variation_id is not null
      then
        if l_node.starting_fen is not null
        then
          raise_application_error(-20023,'Only a root variation may define a starting FEN.');
        end if;
        select * into l_parent from chess_variation
        where variation_id=l_node.parent_variation_id;
        validate_branch(l_parent.pgn,l_node.pgn,l_node.branch_ply,l_root.starting_fen);
      end if;
    end loop;
  exception
    when no_data_found then
      raise_application_error(-20008,'A variation or its ancestor does not exist.');
  end validate_variation_tree;
  procedure validate_image_structure(p_content blob,p_mime varchar2) is
    type crc_table_type is table of number index by binary_integer;
    l_crc_table crc_table_type;
    l_size number := dbms_lob.getlength(p_content);
    l_at number;
    l_length number;
    l_type varchar2(8);
    l_crc number;
    l_value number;
    l_width number;
    l_height number;
    l_depth number;
    l_color number;
    l_marker number;
    l_count number := 0;
    l_seen_header boolean := false;
    l_seen_data boolean := false;
    l_data_ended boolean := false;
    l_seen_palette boolean := false;
    l_seen_scan boolean := false;
    l_entropy number := 0;
    l_components number;
    type component_set is table of boolean index by binary_integer;
    l_frame_components component_set;
    l_scan_components component_set;
    l_delivered_components component_set;
    l_quant_tables component_set;
    l_huff_tables component_set;
    type component_quant_map is table of number index by binary_integer;
    l_component_quant component_quant_map;
    l_table_selector number;
    l_quant_seen boolean := false;
    l_huff_seen boolean := false;
    l_table_at number;
    l_table_width number;
    l_symbols number;
    l_slots number;
    l_component number;
    l_frame_kind number;
    l_hex varchar2(32767);
    l_offset number;
    function byte_at(p_at number) return number is
    begin
      if p_at<1 or p_at>l_size then
        raise_application_error(-20007,'Truncated image content.');
      end if;
      return to_number(rawtohex(dbms_lob.substr(p_content,1,p_at)),'XX');
    end;
    function unsigned_at(p_at number,p_bytes number) return number is
    begin
      if p_at<1 or p_at+p_bytes-1>l_size then
        raise_application_error(-20007,'Truncated image content.');
      end if;
      return to_number(rawtohex(dbms_lob.substr(p_content,p_bytes,p_at)),rpad('X',p_bytes*2,'X'));
    end;
    function xor_value(p_left number,p_right number) return number is
    begin
      return p_left+p_right-2*bitand(p_left,p_right);
    end;
    procedure require_value(p_ok boolean,p_message varchar2) is
    begin
      if p_ok is null or not p_ok then
        raise_application_error(-20007,p_message);
      end if;
    end;
  begin
    if p_mime='image/png'
    then
      require_value(rawtohex(dbms_lob.substr(p_content,8,1))='89504E470D0A1A0A','Invalid PNG signature.');
      for i in 0..255 loop
        l_crc := i;
        for j in 1..8 loop
          if mod(l_crc,2)=1 then l_crc:=xor_value(floor(l_crc/2),3988292384);
          else l_crc:=floor(l_crc/2); end if;
        end loop;
        l_crc_table(i):=l_crc;
      end loop;
      l_at:=9;
      loop
        l_count:=l_count+1;
        require_value(l_count<=4096 and l_at+11<=l_size,'Invalid PNG chunk sequence.');
        l_length:=unsigned_at(l_at,4);
        require_value(l_length<=l_size-l_at-11,'Truncated PNG chunk.');
        l_type:=rawtohex(dbms_lob.substr(p_content,4,l_at+4));
        require_value(regexp_like(utl_raw.cast_to_varchar2(dbms_lob.substr(p_content,4,l_at+4)),'^[A-Za-z]{4}$'),'Invalid PNG chunk type.');
        require_value(l_seen_header or l_type='49484452','PNG must begin with IHDR.');
        l_crc:=4294967295;
        l_offset:=l_at+4;
        while l_offset<l_at+8+l_length loop
          l_hex:=rawtohex(dbms_lob.substr(p_content,least(16000,l_at+8+l_length-l_offset),l_offset));
          for j in 0..length(l_hex)/2-1 loop
            l_crc:=xor_value(floor(l_crc/256),l_crc_table(xor_value(mod(l_crc,256),to_number(substr(l_hex,j*2+1,2),'XX'))));
          end loop;
          l_offset:=l_offset+length(l_hex)/2;
        end loop;
        require_value(xor_value(l_crc,4294967295)=unsigned_at(l_at+8+l_length,4),'PNG chunk checksum is invalid.');
        if l_type='49484452' then
          require_value(not l_seen_header and l_length=13,'Invalid PNG IHDR.');
          l_width:=unsigned_at(l_at+8,4);l_height:=unsigned_at(l_at+12,4);
          l_depth:=byte_at(l_at+16);l_color:=byte_at(l_at+17);
          require_value(l_width>0 and l_height>0 and l_width*l_height<=16000000,'Image exceeds the 16 megapixel limit.');
          require_value((l_color=0 and l_depth in (1,2,4,8,16)) or (l_color in (2,4,6) and l_depth in (8,16)) or (l_color=3 and l_depth in (1,2,4,8)),'Unsupported PNG color format.');
          require_value(byte_at(l_at+18)=0 and byte_at(l_at+19)=0 and byte_at(l_at+20) in (0,1),'Unsupported PNG compression/filter/interlace.');
          l_seen_header:=true;
        elsif l_type='504C5445' then
          require_value(not l_seen_data and not l_seen_palette and mod(l_length,3)=0 and l_length between 3 and 768,'Invalid PNG palette.');
          require_value(l_color not in (0,4),'PNG grayscale cannot contain a palette.');
          l_seen_palette:=true;
        elsif l_type='49444154' then
          require_value(not l_data_ended and (l_color!=3 or l_seen_palette),'Invalid PNG data ordering.');
          if not l_seen_data then
            require_value(l_length>=2 and mod(unsigned_at(l_at+8,2),31)=0 and mod(byte_at(l_at+8),16)=8 and bitand(byte_at(l_at+9),32)=0,'Invalid PNG zlib header.');
          end if;
          l_seen_data:=true;
        elsif l_type='49454E44' then
          require_value(l_length=0 and l_seen_data and l_at+11=l_size,'Invalid PNG IEND or trailing content.');
          exit;
        else
          require_value(bitand(byte_at(l_at+4),32)=32,'Unsupported critical PNG chunk.');
          if l_seen_data then l_data_ended:=true; end if;
        end if;
        l_at:=l_at+12+l_length;
      end loop;
    elsif p_mime='image/jpeg'
    then
      require_value(unsigned_at(1,2)=65496,'Invalid JPEG signature.');
      l_at:=3;
      loop
        require_value(byte_at(l_at)=255,'Invalid JPEG marker.');
        while byte_at(l_at)=255 loop l_at:=l_at+1; end loop;
        l_marker:=byte_at(l_at);l_at:=l_at+1;
        if l_marker=217 then
          require_value(l_seen_header and l_seen_scan and l_entropy>0 and l_delivered_components.count=l_components and l_at=l_size+1,'Invalid JPEG end or trailing content.');
          exit;
        end if;
        require_value(l_marker not in (0,216) and l_marker not between 208 and 215,'Unexpected JPEG marker.');
        l_length:=unsigned_at(l_at,2);
        require_value(l_length>=2 and l_at+l_length-1<=l_size,'Truncated JPEG segment.');
        if l_marker in (192,194) then
          require_value(not l_seen_header and l_length>=11 and byte_at(l_at+2)=8,'Unsupported JPEG frame.');
          l_height:=unsigned_at(l_at+3,2);l_width:=unsigned_at(l_at+5,2);l_components:=byte_at(l_at+7);
          require_value(l_components in (1,3,4) and l_length=8+3*l_components,'Invalid JPEG component table.');
          require_value(l_width>0 and l_height>0 and l_width*l_height<=16000000,'Image exceeds the 16 megapixel limit.');
          for j in 0..l_components-1 loop
            l_component:=byte_at(l_at+8+3*j);
            require_value(not l_frame_components.exists(l_component),'Duplicate JPEG frame component.');
            l_frame_components(l_component):=true;
            l_component_quant(l_component):=byte_at(l_at+10+3*j);
            l_value:=byte_at(l_at+9+3*j);
            require_value(floor(l_value/16) between 1 and 4 and mod(l_value,16) between 1 and 4 and byte_at(l_at+10+3*j)<=3,'Invalid JPEG sampling table.');
          end loop;
          l_seen_header:=true;
          l_frame_kind:=l_marker;
        elsif l_marker=219 then
          l_table_at:=l_at+2;
          require_value(l_length>2,'Empty JPEG quantization segment.');
          while l_table_at<l_at+l_length loop
            l_value:=byte_at(l_table_at);
            require_value(floor(l_value/16) in (0,1) and mod(l_value,16)<=3,'Invalid JPEG quantization selector.');
            l_quant_tables(mod(l_value,16)):=true;
            l_table_width:=1+floor(l_value/16);
            require_value(l_table_at+1+64*l_table_width<=l_at+l_length,'Truncated JPEG quantization table.');
            for j in 0..63 loop
              require_value(unsigned_at(l_table_at+1+j*l_table_width,l_table_width)>0,'Zero JPEG quantization value.');
            end loop;
            l_table_at:=l_table_at+1+64*l_table_width;
          end loop;
          require_value(l_table_at=l_at+l_length,'Invalid JPEG quantization segment length.');
          l_quant_seen:=true;
        elsif l_marker=196 then
          l_table_at:=l_at+2;
          require_value(l_length>2,'Empty JPEG Huffman segment.');
          while l_table_at<l_at+l_length loop
            l_value:=byte_at(l_table_at);
            require_value(floor(l_value/16) in (0,1) and mod(l_value,16)<=3 and l_table_at+17<=l_at+l_length,'Invalid JPEG Huffman selector.');
            l_table_selector:=floor(l_value/16)*4+mod(l_value,16);
            l_symbols:=0;l_slots:=1;
            for j in 1..16 loop
              l_value:=byte_at(l_table_at+j);
              l_symbols:=l_symbols+l_value;
              l_slots:=l_slots*2-l_value;
              require_value(l_slots>=0,'Oversubscribed JPEG Huffman tree.');
            end loop;
            require_value(l_symbols between 1 and 256 and l_table_at+17+l_symbols<=l_at+l_length,'Truncated JPEG Huffman symbols.');
            l_huff_tables(l_table_selector):=true;
            l_table_at:=l_table_at+17+l_symbols;
          end loop;
          require_value(l_table_at=l_at+l_length,'Invalid JPEG Huffman segment length.');
          l_huff_seen:=true;
        elsif l_marker between 192 and 207 and l_marker not in (196,204) then
          raise_application_error(-20007,'Unsupported JPEG frame encoding.');
        elsif l_marker=218 then
          require_value(l_seen_header and l_quant_seen and l_huff_seen,'JPEG scan requires its frame, quantization and Huffman tables.');
          l_value:=byte_at(l_at+2);
          require_value(l_value between 1 and l_components and l_length=6+2*l_value,'Invalid JPEG scan header.');
          l_scan_components.delete;
          for j in 0..l_value-1 loop
            l_component:=byte_at(l_at+3+2*j);
            require_value(l_frame_components.exists(l_component) and not l_scan_components.exists(l_component),'Invalid JPEG scan component.');
            l_scan_components(l_component):=true;
            l_delivered_components(l_component):=true;
            require_value(floor(byte_at(l_at+4+2*j)/16)<=3 and mod(byte_at(l_at+4+2*j),16)<=3,'Invalid JPEG Huffman table reference.');
            require_value(l_quant_tables.exists(l_component_quant(l_component)),'Missing JPEG quantization table reference.');
            if byte_at(l_at+3+2*l_value)=0 then
              require_value(l_huff_tables.exists(floor(byte_at(l_at+4+2*j)/16)),'Missing JPEG DC Huffman table.');
            end if;
            if byte_at(l_at+4+2*l_value)>0 then
              require_value(l_huff_tables.exists(4+mod(byte_at(l_at+4+2*j),16)),'Missing JPEG AC Huffman table.');
            end if;
          end loop;
          if l_frame_kind=192 then
            require_value(byte_at(l_at+3+2*l_value)=0 and byte_at(l_at+4+2*l_value)=63 and byte_at(l_at+5+2*l_value)=0,'Invalid baseline JPEG scan parameters.');
          else
            require_value(byte_at(l_at+3+2*l_value)<=byte_at(l_at+4+2*l_value) and byte_at(l_at+4+2*l_value)<=63,'Invalid progressive JPEG spectral range.');
            require_value((byte_at(l_at+3+2*l_value)=0 and byte_at(l_at+4+2*l_value)=0) or l_value=1,'Invalid progressive JPEG component scan.');
          end if;
          l_seen_scan:=true;
        elsif l_marker=221 then
          require_value(l_length=4,'Invalid JPEG restart interval.');
        end if;
        l_at:=l_at+l_length;
        if l_marker=218 then
          loop
            l_value:=byte_at(l_at);l_at:=l_at+1;
            if l_value=255 then
              if byte_at(l_at)=0 then l_at:=l_at+1;l_entropy:=l_entropy+1;
              elsif byte_at(l_at) between 208 and 215 then l_at:=l_at+1;
              else l_at:=l_at-1;exit; end if;
            else l_entropy:=l_entropy+1;
            end if;
          end loop;
        end if;
      end loop;
    else
      raise_application_error(-20007,'Only PNG and JPEG content is supported.');
    end if;
  end;
  procedure validate_image(p_content blob, p_mime varchar2, p_alt varchar2) is
    l_max number;
    l_size number;
  begin
    if trim(p_alt) is null
    then
      raise_application_error(-20005, 'Image alternative text is required.');
    end if;
    select max_image_bytes into l_max from chess_admin_control where control_id=1;
    l_size := dbms_lob.getlength(p_content);
    if p_content is null or l_size is null or l_size=0 or l_size>l_max
    then
      raise_application_error(-20006, 'Image is empty or exceeds the configured size limit.');
    end if;
    validate_image_structure(p_content,p_mime);
  end;

end chess_validation_api;
/
--rollback drop package body orac_chess.chess_validation_api;
