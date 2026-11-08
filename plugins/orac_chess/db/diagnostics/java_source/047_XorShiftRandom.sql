--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_047_XorShiftRandom context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "com/github/bhlangonijr/chesslib/util/XorShiftRandom" as
package com.github.bhlangonijr.chesslib.util;
/**
 * A utility class that is used to generate pseudorandom numbers bases on XOR and bit shifts operations.
 * <a href="https://en.wikipedia.org/wiki/Xorshift">Xorshift random generators</a> are simple and efficient software
 * implementations of number generators.
 */
public class XorShiftRandom {
    private long seed;
    /**
     * Constructs a new random number generator using a custom long seed.
     *
     * @param seed the initial seed
     */
    public XorShiftRandom(long seed) {
        this.seed = seed;
    }
    /**
     * Constructs a new random number generator.
     */
    public XorShiftRandom() {
        this(System.nanoTime());
    }
    /**
     * Returns the next pseudorandom long value from this random number generator''s sequence.
     *
     * @return the next pseudorandom long value
     */
    public long nextLong() {
        seed ^= seed >>> 12;
        seed ^= seed << 25;
        seed ^= seed >>> 27;
        return seed * 0x2545F4914F6CDD1DL;
    }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "com/github/bhlangonijr/chesslib/util/XorShiftRandom";
