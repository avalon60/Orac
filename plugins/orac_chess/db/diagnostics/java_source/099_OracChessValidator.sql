--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Generated pinned Java source; edit upstream or adapter source.
-- Purpose: Source-only Oracle JVM chess validation with no external permissions.
-- Usage: Managed plugin Liquibase controller; regenerate using tools/generate_java_sources.py.

--changeset clive:orac_chess_java_099_OracChessValidator context:plugin,prod labels:plugin runOnChange:true stripComments:false endDelimiter:/
declare
  l_source clob;
begin
  l_source := l_source || to_clob('create or replace java source named "OracChessValidator" as
/** Authoritative, strictly consumed PGN validation backed by chesslib legal moves.
 * Author: Clive Bostock
 * Date: 02-Nov-2026
 * Purpose: Validate complete PGNs, every RAV and relational branch prefixes in Oracle JVM.
 * Usage: Called by the private chess_validation_api; caller owns the transaction.
 */
import com.github.bhlangonijr.chesslib.*;
import com.github.bhlangonijr.chesslib.move.*;
import java.sql.Clob;
import java.util.*;
import java.util.regex.*;
public final class OracChessValidator {
  private static final String START = Constants.startStandardFENPosition;
  private static final Pattern TAG = Pattern.compile("\\[([A-Za-z][A-Za-z0-9_]*)\\s+\"((?:[^\"\\\\\\r\\n]|\\\\[\"\\\\])*)\"\\s*\\]");
  private static final Pattern TOKEN = Pattern.compile("1/2-1/2|1-0|0-1|\\*|[0-9]+\\.(?:\\.\\.)?|\\$[0-9]+|[!?]{1,2}|(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)[+#]?[!?]{0,2}");
  private final String text;
  private int at;
  private final Map<String,String> tags = new LinkedHashMap<>();
  private final boolean single;
  private List<String> mainMoves;
  private List<String> mainPositions;
  private OracChessValidator(String text, boolean single) {
    this.text=text; this.single=single;
  }
  private static void need(boolean ok,String message) {
    if (!ok) throw new IllegalArgumentException(message);
  }
  private void space() {
    while(at<text.length()) {
      char c=text.charAt(at);
      if(Character.isWhitespace(c)) { at++; continue; }
      if(c=='';'') { while(at<text.length() && text.charAt(at)!=''\n'' && text.charAt(at)!=''\r'') at++; continue; }
      if(c==''{'') {
        int end=text.indexOf(''}'',at+1);
        need(end>=0,"Unclosed PGN comment");
        need(text.indexOf(''{'',at+1)<0 || text.indexOf(''{'',at+1)>end,"Nested brace comment");
        at=end+1; continue;
      }
      break;
    }
  }
  private String token() {
    space();
    if(at==text.length()) return null;
    char c=text.charAt(at);
    if(c==''('' || c=='')'') {at++;return String.valueOf(c);}
    Matcher m=TOKEN.matcher(text);m.region(at,text.length());
    need(m.lookingAt(),"Invalid PGN token at character "+(at+1));
    String token=m.group();at=m.end();
    need(at==text.length() || Character.isWhitespace(text.charAt(at)) || "{}();$!?".indexOf(text.charAt(at))>=0 || token.endsWith("."), "Missing PGN token separator");
    return token;
  }
  private static Board position(String fen) {
    need(fen!=null && fen.matches("[prnbqkPRNBQK1-8]+(?:/[prnbqkPRNBQK1-8]+){7} [wb] (?:-|K?Q?k?q?) (?:-|[a-h][36]) [0-9]+ [1-9][0-9]*"),"Invalid FEN syntax");
    String[] parts=fen.split(" ");
    String[] ranks=parts[0].split("/");
    for(String rank:ranks) {
      int n=0; boolean digit=false;
      for(char c:rank.toCharArray()) {
        boolean now=Character.isDigit(c);
        need(!(digit&&now),"Noncanonical FEN empty squares");
        n+=now?c-''0'':1;digit=now;
      }
      need(n==8,"Invalid FEN rank width");
    }
    for(char king:new char[]{''K'',''k''}) need(parts[0].chars().filter(c->c==king).count()==1,"FEN requires one king per side");
    need(!ranks[0].matches(".*[Pp].*")&&!ranks[7].matches(".*[Pp].*"),"FEN has pawn on promotion rank");
    for(char pawn:new char[]{''P'',''p''}) need(parts[0].chars().filter(c->c==pawn).count()<=8,"Too many FEN pawns");
    need(parts[0].chars().filter(Character::isUpperCase).count()<=16 && parts[0].chars().filter(Character::isLowerCase).count()<=16,"Too many FEN pieces");
    Board b=new Board();b.loadFromFen(fen);
    need(b.squareAttackedBy(b.getKingSquare(b.getSideToMove().flip()),b.getSideToMove())==0,"FEN leaves the side that just moved in check");
    String rights=parts[2];
    if(rights.contains("K")) need(b.getPiece(Square.E1)==Piece.WHITE_KING&&b.getPiece(Square.H1)==Piece.WHITE_ROOK,"Invalid white king-side castling right");
    if(rights.contains("Q")) need(b.getPiece(Square.E1)==Piece.WHITE_KING&&b.getPiece(Square.A1)==Piece.WHITE_ROO');
  l_source := l_source || to_clob('K,"Invalid white queen-side castling right");
    if(rights.contains("k")) need(b.getPiece(Square.E8)==Piece.BLACK_KING&&b.getPiece(Square.H8)==Piece.BLACK_ROOK,"Invalid black king-side castling right");
    if(rights.contains("q")) need(b.getPiece(Square.E8)==Piece.BLACK_KING&&b.getPiece(Square.A8)==Piece.BLACK_ROOK,"Invalid black queen-side castling right");
    if(!parts[3].equals("-")) {
      int file=parts[3].charAt(0)-''a'';boolean white=b.getSideToMove()==Side.WHITE;
      need(parts[3].charAt(1)==(white?''6'':''3''),"FEN en passant rank conflicts with side");
      need(b.getPiece(Square.squareAt((white?4:3)*8+file))==(white?Piece.BLACK_PAWN:Piece.WHITE_PAWN),"FEN en passant pawn is absent");
      need(b.getPiece(Square.squareAt((white?6:1)*8+file))==Piece.NONE && b.getPiece(Square.valueOf(parts[3].toUpperCase()))==Piece.NONE,"Invalid FEN en passant origin or target");
      need(parts[4].equals("0"),"FEN en passant requires zero halfmove clock");
    }
    return b;
  }
  private String parseLine(String fen,int depth) {
    need(depth<=64,"PGN RAV nesting exceeds 64");
    Board board=position(fen);
    String previous=null,result=null;
    boolean numberPending=false;
    List<String> moves=new ArrayList<>(); List<String> positions=new ArrayList<>();positions.add(board.getFen());
    while(true) {
      String t=token();
      if(t==null || t.equals(")")) {
        need(!numberPending,"Move number has no move");
        need(depth>0?t!=null:t==null,"Unbalanced PGN variation");
        if(depth==0) need(result!=null,"Complete PGN requires a terminal result");
        break;
      }
      if(t.equals("(")) {
        need(result==null,"RAV after PGN result");
        need(!single,"Relational variation PGN must contain one mainline without RAV");
        need(previous!=null&&!numberPending,"RAV must follow a move");
        parseLine(previous,depth+1);continue;
      }
      need(result==null,"Tokens after PGN result");
      if(t.matches("[0-9]+\\..*")) {
        need(!numberPending,"Repeated move number");
        String[] state=board.getFen().split(" ");
        need(t.equals(state[5]+(board.getSideToMove()==Side.WHITE?".":"...")),"Move number conflicts with position");
        numberPending=true;continue;
      }
      if(t.startsWith("$")||t.matches("[!?]+")) {need(previous!=null&&!numberPending,"Annotation without a move");continue;}
      if(t.equals("*")||t.equals("1-0")||t.equals("0-1")||t.equals("1/2-1/2")) {need(!numberPending,"Result after incomplete move number");result=t;continue;}
      String san=t.replaceFirst("[!?]+$","");
      String before=board.getFen();
      MoveList decoded=new MoveList(before);decoded.addSanMove(san,true,true);
      need(decoded.size()==1,"PGN move was not fully consumed");
      Move move=decoded.getFirst();need(board.legalMoves().contains(move),"Illegal move: "+san);
      MoveList canonical=new MoveList(before);canonical.add(new Move(move.getFrom(),move.getTo(),move.getPromotion()));
      need(canonical.toSanArray()[0].equals(san),"Invalid or ambiguous SAN: "+san);
      need(board.doMove(move,true),"Illegal move: "+san);
      previous=before;numberPending=false;moves.add(move.toString());positions.add(board.getFen());
    }
    need(!moves.isEmpty(),"PGN line has no moves");
    if(depth==0) {mainMoves=moves;mainPositions=positions;}
    return result;
  }
  private void parse(String expectedFen) {
    space();
    while(at<text.length()&&text.charAt(at)==''['') {
      Matcher m=TAG.matcher(text);m.region(at,text.length());need(m.lookingAt(),"Invalid PGN header");
      String value=m.group(2).replace("\\\"","\"").replace("\\\\","\\");
      need(!tags.containsKey(m.group(1)),"Duplicate PGN header");tags.put(m.group(1),value);at=m.end();space();
    }
    String fen=tags.get("FEN");String setup=tags.get("SetUp");
    need((fen==null&&setup==null)||(fen!=null&&"1".equals(setup)),"FEN and SetUp 1 must occur together");
    if(expectedFen!=null) {position(expectedFen);need(expect');
  l_source := l_source || to_clob('edFen.equals(fen),"PGN FEN does not match inherited root FEN");}
    else need(fen==null || !single,"Variation FEN must match its root starting FEN");
    String result=parseLine(fen==null?START:fen,0);
    need(!tags.containsKey("Result")||tags.get("Result").equals(result),"Result header differs from movetext result");
  }
  private static OracChessValidator parsed(Clob text,int single,String fen) throws Exception {
    need(text!=null&&text.length()>0&&text.length()<=4194304,"PGN must contain 1 to 4194304 characters");
    OracChessValidator p=new OracChessValidator(text.getSubString(1,(int)text.length()),single==1);p.parse(fen);return p;
  }
  public static String validate(Clob text,int single,String fen) {
    try {parsed(text,single,fen);return null;} catch(Exception e) {return safe(e);}
  }
  public static String branch(Clob parent,Clob child,int ply,String fen) {
    try {
      OracChessValidator p=parsed(parent,1,fen),c=parsed(child,1,fen);
      need(ply>=0&&ply<p.mainMoves.size()&&ply<c.mainMoves.size(),"Branch must diverge before the parent ends");
      need(p.mainMoves.subList(0,ply).equals(c.mainMoves.subList(0,ply))&&p.mainPositions.get(ply).equals(c.mainPositions.get(ply)),"Branch prefix differs from parent");
      need(!p.mainMoves.get(ply).equals(c.mainMoves.get(ply)),"Branch must differ on its next half-move");return null;
    } catch(Exception e) {return safe(e);}
  }
  public static String continuation(Clob parent,Clob child,int ply,String fen) {
    try {
      OracChessValidator p=parsed(parent,1,fen),c=parsed(child,1,fen);
      need(ply==p.mainMoves.size(),"Continuation ply must equal parent length");
      need(c.mainMoves.size()>ply,"Continuation must extend the complete parent");
      need(p.mainMoves.equals(c.mainMoves.subList(0,ply))&&
        p.mainPositions.equals(c.mainPositions.subList(0,ply+1)),"Continuation prefix differs");
      return null;
    } catch(Exception e) {return safe(e);}
  }
  public static String header(Clob text,String name) {
    try {return parsed(text,0,null).tags.get(name);} catch(Exception e) {throw new IllegalArgumentException(safe(e));}
  }
  private static String safe(Exception e) {
    String m=e.getMessage();return (m==null?"Invalid PGN/FEN":m).substring(0,Math.min(700,m==null?15:m.length()));
  }
}');
  execute immediate l_source;
end;
/
--rollback drop java source "OracChessValidator";
