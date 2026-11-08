--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_044_PgnProperty context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "com/github/bhlangonijr/chesslib/pgn/PgnProperty" as
package com.github.bhlangonijr.chesslib.pgn;
import java.util.regex.Pattern;
import com.github.bhlangonijr.chesslib.util.StringUtil;
import org.apache.commons.lang3.StringUtils;
/**
 * The definition of a Portable Game Notation (PGN) property, also known as <i>tag</i>.
 */
public class PgnProperty {
    /**
     * The Byte Order Mark (BOM) that defines a big-endian representation of bytes.
     */
    public final static String UTF8_BOM = "\uFEFF";
    private final static Pattern propertyPattern = Pattern.compile("\\[.* \".*\"\\]");
    /**
     * The name of the PGN property.
     */
    public String name;
    /**
     * The value of the PGN property.
     */
    public String value;
    /**
     * Constructs an empty PGN property.
     */
    public PgnProperty() {
    }
    /**
     * Constructs an PGN property formed by a tag pair.
     *
     * @param name  the name of the property
     * @param value the value of the property
     */
    public PgnProperty(String name, String value) {
        this.name = name;
        this.value = value;
    }
    /**
     * Checks if the line of text contains a PGN property.
     *
     * @param line the line of text to check
     * @return {@code true} if the line is a PGN property
     */
    public static boolean isProperty(String line) {
        return propertyPattern.matcher(line).matches();
    }
    /**
     * Parses a line of text that contains a PGN property.
     *
     * @param line the line of text that includes the PGN property
     * @return the PGN property extracted from the line of text
     */
    public static PgnProperty parsePgnProperty(String line) {
        try {
            String l = line.replace("[", StringUtils.EMPTY);
            l = l.replace("]", StringUtils.EMPTY);
            l = l.replace("\"", StringUtils.EMPTY);
            return new PgnProperty(StringUtil.beforeSequence(l, StringUtils.SPACE),
                    StringUtil.afterSequence(l, StringUtils.SPACE));
        } catch (Exception e) {
            // do nothing
        }
        return null;
    }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "com/github/bhlangonijr/chesslib/pgn/PgnProperty";
