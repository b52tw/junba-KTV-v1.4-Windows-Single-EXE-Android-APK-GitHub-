package tw.junba.ktvmultitrack

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

object Review {
    private val speakerPrefix = Regex("^\\s*(?:(?:spk|speaker)\\s*[:#-]?\\s*\\d+|(?:講者|說話者)\\s*\\d+)\\s*[：:]\\s*", RegexOption.IGNORE_CASE)
    private fun norm(s:String)=s.lowercase().replace(speakerPrefix,"").replace(Regex("""[\s　，。！？；：、,.!?;:\"“”‘’()（）\[\]【】<>《》…—-]+"""),"")
    private fun levenshtein(a:String,b:String):Int{if(a.isEmpty())return b.length;if(b.isEmpty())return a.length;var prev=IntArray(b.length+1){it};for(i in a.indices){val cur=IntArray(b.length+1);cur[0]=i+1;for(j in b.indices){cur[j+1]=minOf(cur[j]+1,prev[j+1]+1,prev[j]+if(a[i]==b[j])0 else 1)};prev=cur};return prev[b.length]}
    fun similarity(a:String,b:String):Double{val x=norm(a);val y=norm(b);if(x.isEmpty()&&y.isEmpty())return 1.0;if(x.isEmpty()||y.isEmpty())return 0.0;return 1.0-levenshtein(x,y).toDouble()/max(x.length,y.length)}

    private fun window(s:Segment):Pair<Double,Double>{val e=if(s.end>s.start)s.end else s.start+.8;return s.start to e}
    fun matchText(s:Segment,t:TextTrack,tolerance:Double=.35):String{
        if(t.segments.isEmpty())return ""
        val (a0,a1)=window(s)
        val hits=t.segments.filter{b->val (b0,b1)=window(b);min(a1+tolerance,b1+tolerance)-max(a0-tolerance,b0-tolerance)>0}.sortedBy{it.start}
        if(hits.isNotEmpty())return hits.joinToString(" "){it.text.trim()}.trim()
        val mid=(a0+a1)/2
        return t.segments.minByOrNull{abs(it.start-mid)}?.text?.trim().orEmpty()
    }
    fun compare(a:TextTrack,b:TextTrack):List<ReviewResult>{
        if(a===b)return a.segments.map{ReviewResult(1.0,"green",it.text,"同一文字軌")}
        return a.segments.map{s->val other=matchText(s,b);if(other.isBlank())ReviewResult(0.0,"red","","找不到同時間文字") else {val sc=similarity(s.text,other);val lv=if(sc>=.82)"green" else if(sc>=.55)"yellow" else "red";ReviewResult(sc,lv,other,if(lv=="green")"高度吻合" else if(lv=="yellow")"內容接近，建議聽音核對" else "文字差異較大；不等於一定漏字")}}
    }
}
