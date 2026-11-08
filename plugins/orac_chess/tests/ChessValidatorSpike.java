/** Regression corpus for strict PGN consumption and legal branch replay.
 * Author: Clive Bostock
 * Date: 02-Nov-2026
 * Purpose: Exercise shipped adapter against pinned source dependencies.
 * Usage: pytest tests/test_orac_chess_validator.py
 */
import javax.sql.rowset.serial.SerialClob;
public class ChessValidatorSpike {
  static int count;
  static SerialClob clob(String s) throws Exception { return new SerialClob(s.toCharArray()); }
  static void check(String p, boolean valid, int single, String fen) throws Exception {
    String error=OracChessValidator.validate(clob(p),single,fen);
    if((error==null)!=valid) throw new AssertionError(p+" -> "+error);
    count++;
  }
  public static void main(String[] args) throws Exception {
    check("1. e4 e5 2. Nf3 Nc6 *",true,1,null);
    check("1.e4 {comment} e5 $1 2.Nf3!? Nc6 *",true,1,null);
    check("1.e4 (1.d4 d5 (1...Nf6)) e5 *",true,0,null);
    check("1.e4 (1.d4 d5 (1...Nf6)) e5 *",false,1,null);
    check("1.e4 (1.d4 Ke7) e5 *",false,0,null);
    check("1.e4 e5 * trailing",false,0,null);
    check("1.e4 e5 * 1.d4",false,0,null);
    check("1.e4# e5 *",false,0,null);
    check("1.e4 e5 2.Ne3 *",false,0,null);
    check("1.e4 e5",false,0,null);
    check("1.e4 {unterminated e5 *",false,0,null);
    check("1.e4 (1.d4 e5 *",false,0,null);
    check("[Result \"1-0\"]\n1.e4 e5 *",false,0,null);
    check("[FEN \"8/8/8/8/8/8/8/K6k w - - 0 1\"]\n1.Kb1 *",false,0,null);
    String fen="8/8/8/8/8/8/8/K6k w - - 0 1";
    check("[SetUp \"1\"] [FEN \""+fen+"\"] 1.Kb1 *",true,1,fen);
    check("[SetUp \"1\"] [FEN \"8/8/8/8/8/8/8/KK5k w - - 0 1\"] 1.Kb1 *",false,0,null);
    check("1.e4e5 *",false,0,null);
    check("1.e4 * (1.d4)",false,0,null);
    check("1.e4 (1.d4 (1.c4 e5) d5) e5 *",true,0,null);
    check("1.e4 (1.d4 (1.c4 Ke7) d5) e5 *",false,0,null);
    check("1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O *",true,0,null);
    check("1.O-O *",false,0,null);
    check("1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7# 1-0",true,0,null);
    check("1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7+ 1-0",false,0,null);
    check("[SetUp \"1\"] [FEN \"8/8/8/8/8/8/8/K6k w K - 0 1\"] 1.Kb1 *",false,0,null);
    check("[SetUp \"1\"] [FEN \"8/8/8/8/8/8/8/K6k w - e6 0 1\"] 1.Kb1 *",false,0,null);
    check("[SetUp \"1\"] [FEN \"8/8/8/8/8/8/8/Kk6 w - - 0 1\"] 1.Kb1 *",false,0,null);
    if(OracChessValidator.branch(clob("1.e4 e5 2.Nf3 *"),clob("1.e4 c5 *"),1,null)!=null) throw new AssertionError("valid branch");count++;
    if(OracChessValidator.branch(clob("1.e4 e5 *"),clob("1.e4 e5 2.Nf3 *"),2,null)==null) throw new AssertionError("extension accepted");count++;
    System.out.println(count+" validator spike checks passed");
  }
}
