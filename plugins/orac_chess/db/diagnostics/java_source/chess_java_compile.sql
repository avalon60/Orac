--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_compile_001_Bitboard context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Bitboard" compile;

--changeset clive:orac_chess_java_compile_002_Board context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Board" compile;

--changeset clive:orac_chess_java_compile_003_BoardEvent context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/BoardEvent" compile;

--changeset clive:orac_chess_java_compile_004_BoardEventListener context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/BoardEventListener" compile;

--changeset clive:orac_chess_java_compile_005_BoardEventType context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/BoardEventType" compile;

--changeset clive:orac_chess_java_compile_006_CastleRight context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/CastleRight" compile;

--changeset clive:orac_chess_java_compile_007_Constants context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Constants" compile;

--changeset clive:orac_chess_java_compile_008_DiagonalA1H8 context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/DiagonalA1H8" compile;

--changeset clive:orac_chess_java_compile_009_DiagonalH1A8 context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/DiagonalH1A8" compile;

--changeset clive:orac_chess_java_compile_010_File context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/File" compile;

--changeset clive:orac_chess_java_compile_011_MoveBackup context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/MoveBackup" compile;

--changeset clive:orac_chess_java_compile_012_Piece context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Piece" compile;

--changeset clive:orac_chess_java_compile_013_PieceType context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/PieceType" compile;

--changeset clive:orac_chess_java_compile_014_Rank context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Rank" compile;

--changeset clive:orac_chess_java_compile_015_Side context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Side" compile;

--changeset clive:orac_chess_java_compile_016_Square context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/Square" compile;

--changeset clive:orac_chess_java_compile_017_Event context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/Event" compile;

--changeset clive:orac_chess_java_compile_018_EventType context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/EventType" compile;

--changeset clive:orac_chess_java_compile_019_Game context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/Game" compile;

--changeset clive:orac_chess_java_compile_020_GameContext context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/GameContext" compile;

--changeset clive:orac_chess_java_compile_021_GameFactory context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/GameFactory" compile;

--changeset clive:orac_chess_java_compile_022_GameMode context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/GameMode" compile;

--changeset clive:orac_chess_java_compile_023_GameResult context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/GameResult" compile;

--changeset clive:orac_chess_java_compile_024_GenericPlayer context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/GenericPlayer" compile;

--changeset clive:orac_chess_java_compile_025_MovePerTime context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/MovePerTime" compile;

--changeset clive:orac_chess_java_compile_026_Player context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/Player" compile;

--changeset clive:orac_chess_java_compile_027_PlayerType context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/PlayerType" compile;

--changeset clive:orac_chess_java_compile_028_Round context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/Round" compile;

--changeset clive:orac_chess_java_compile_029_Termination context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/Termination" compile;

--changeset clive:orac_chess_java_compile_030_TimeControl context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/TimeControl" compile;

--changeset clive:orac_chess_java_compile_031_TimeControlType context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/TimeControlType" compile;

--changeset clive:orac_chess_java_compile_032_VariationType context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/game/VariationType" compile;

--changeset clive:orac_chess_java_compile_033_Move context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/move/Move" compile;

--changeset clive:orac_chess_java_compile_034_MoveConversionException context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/move/MoveConversionException" compile;

--changeset clive:orac_chess_java_compile_035_MoveException context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/move/MoveException" compile;

--changeset clive:orac_chess_java_compile_036_MoveGenerator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/move/MoveGenerator" compile;

--changeset clive:orac_chess_java_compile_037_MoveGeneratorException context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/move/MoveGeneratorException" compile;

--changeset clive:orac_chess_java_compile_038_MoveList context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/move/MoveList" compile;

--changeset clive:orac_chess_java_compile_039_GameLoader context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/pgn/GameLoader" compile;

--changeset clive:orac_chess_java_compile_040_PgnException context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/pgn/PgnException" compile;

--changeset clive:orac_chess_java_compile_041_PgnHolder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/pgn/PgnHolder" compile;

--changeset clive:orac_chess_java_compile_042_PgnIterator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/pgn/PgnIterator" compile;

--changeset clive:orac_chess_java_compile_043_PgnLoadListener context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/pgn/PgnLoadListener" compile;

--changeset clive:orac_chess_java_compile_044_PgnProperty context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/pgn/PgnProperty" compile;

--changeset clive:orac_chess_java_compile_045_LargeFile context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/util/LargeFile" compile;

--changeset clive:orac_chess_java_compile_046_StringUtil context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/util/StringUtil" compile;

--changeset clive:orac_chess_java_compile_047_XorShiftRandom context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "com/github/bhlangonijr/chesslib/util/XorShiftRandom" compile;

--changeset clive:orac_chess_java_compile_048_ArraySorter context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/ArraySorter" compile;

--changeset clive:orac_chess_java_compile_049_ArrayUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/ArrayUtils" compile;

--changeset clive:orac_chess_java_compile_050_BooleanUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/BooleanUtils" compile;

--changeset clive:orac_chess_java_compile_051_CharSequenceUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/CharSequenceUtils" compile;

--changeset clive:orac_chess_java_compile_052_CharUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/CharUtils" compile;

--changeset clive:orac_chess_java_compile_053_Charsets context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/Charsets" compile;

--changeset clive:orac_chess_java_compile_054_ClassUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/ClassUtils" compile;

--changeset clive:orac_chess_java_compile_055_LocaleUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/LocaleUtils" compile;

--changeset clive:orac_chess_java_compile_056_ObjectUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/ObjectUtils" compile;

--changeset clive:orac_chess_java_compile_057_Range context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/Range" compile;

--changeset clive:orac_chess_java_compile_058_RegExUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/RegExUtils" compile;

--changeset clive:orac_chess_java_compile_059_StringEscapeUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/StringEscapeUtils" compile;

--changeset clive:orac_chess_java_compile_060_StringUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/StringUtils" compile;

--changeset clive:orac_chess_java_compile_061_Validate context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/Validate" compile;

--changeset clive:orac_chess_java_compile_062_Builder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/Builder" compile;

--changeset clive:orac_chess_java_compile_063_CompareToBuilder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/CompareToBuilder" compile;

--changeset clive:orac_chess_java_compile_064_EqualsBuilder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/EqualsBuilder" compile;

--changeset clive:orac_chess_java_compile_065_EqualsExclude context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/EqualsExclude" compile;

--changeset clive:orac_chess_java_compile_066_HashCodeBuilder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/HashCodeBuilder" compile;

--changeset clive:orac_chess_java_compile_067_HashCodeExclude context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/HashCodeExclude" compile;

--changeset clive:orac_chess_java_compile_068_IDKey context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/IDKey" compile;

--changeset clive:orac_chess_java_compile_069_ReflectionToStringBuilder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/ReflectionToStringBuilder" compile;

--changeset clive:orac_chess_java_compile_070_ToStringBuilder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/ToStringBuilder" compile;

--changeset clive:orac_chess_java_compile_071_ToStringExclude context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/ToStringExclude" compile;

--changeset clive:orac_chess_java_compile_072_ToStringStyle context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/ToStringStyle" compile;

--changeset clive:orac_chess_java_compile_073_ToStringSummary context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/builder/ToStringSummary" compile;

--changeset clive:orac_chess_java_compile_074_CloneFailedException context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/exception/CloneFailedException" compile;

--changeset clive:orac_chess_java_compile_075_FailableBiConsumer context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/function/FailableBiConsumer" compile;

--changeset clive:orac_chess_java_compile_076_ToBooleanBiFunction context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/function/ToBooleanBiFunction" compile;

--changeset clive:orac_chess_java_compile_077_NumberUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/math/NumberUtils" compile;

--changeset clive:orac_chess_java_compile_078_Mutable context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/mutable/Mutable" compile;

--changeset clive:orac_chess_java_compile_079_MutableInt context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/mutable/MutableInt" compile;

--changeset clive:orac_chess_java_compile_080_MutableObject context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/mutable/MutableObject" compile;

--changeset clive:orac_chess_java_compile_081_StrBuilder context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/StrBuilder" compile;

--changeset clive:orac_chess_java_compile_082_StrMatcher context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/StrMatcher" compile;

--changeset clive:orac_chess_java_compile_083_StrTokenizer context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/StrTokenizer" compile;

--changeset clive:orac_chess_java_compile_084_AggregateTranslator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/AggregateTranslator" compile;

--changeset clive:orac_chess_java_compile_085_CharSequenceTranslator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/CharSequenceTranslator" compile;

--changeset clive:orac_chess_java_compile_086_CodePointTranslator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/CodePointTranslator" compile;

--changeset clive:orac_chess_java_compile_087_EntityArrays context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/EntityArrays" compile;

--changeset clive:orac_chess_java_compile_088_JavaUnicodeEscaper context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/JavaUnicodeEscaper" compile;

--changeset clive:orac_chess_java_compile_089_LookupTranslator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/LookupTranslator" compile;

--changeset clive:orac_chess_java_compile_090_NumericEntityEscaper context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/NumericEntityEscaper" compile;

--changeset clive:orac_chess_java_compile_091_NumericEntityUnescaper context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/NumericEntityUnescaper" compile;

--changeset clive:orac_chess_java_compile_092_OctalUnescaper context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/OctalUnescaper" compile;

--changeset clive:orac_chess_java_compile_093_UnicodeEscaper context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/UnicodeEscaper" compile;

--changeset clive:orac_chess_java_compile_094_UnicodeUnescaper context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/UnicodeUnescaper" compile;

--changeset clive:orac_chess_java_compile_095_UnicodeUnpairedSurrogateRemover context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/text/translate/UnicodeUnpairedSurrogateRemover" compile;

--changeset clive:orac_chess_java_compile_096_DurationUtils context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/time/DurationUtils" compile;

--changeset clive:orac_chess_java_compile_097_ImmutablePair context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/tuple/ImmutablePair" compile;

--changeset clive:orac_chess_java_compile_098_Pair context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "org/apache/commons/lang3/tuple/Pair" compile;

--changeset clive:orac_chess_java_compile_099_OracChessValidator context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter java source "OracChessValidator" compile;
