package tw.junba.ktvmultitrack

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.view.Gravity
import android.view.WindowInsets
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.BaseAdapter
import android.widget.Button
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private val tracks = mutableListOf<TextTrack>()
    private var audioUri: Uri? = null
    private var player: MediaPlayer? = null
    private val handler = Handler(Looper.getMainLooper())

    private lateinit var fullText: TextView
    private lateinit var fullScroll: ScrollView
    private lateinit var timeline: ListView
    private lateinit var activeSpinner: Spinner
    private lateinit var compareSpinner: Spinner
    private lateinit var seek: SeekBar
    private lateinit var timeLabel: TextView
    private lateinit var summary: TextView
    private lateinit var audioLabel: TextView
    private lateinit var currentCue: TextView

    private var ranges = mutableListOf<Pair<Int, Int>>()
    private var review = listOf<ReviewResult>()
    private var currentIndex = -1
    private var plainFullText = ""
    private var topFollow = true
    private var timelineFollow = true
    private var playbackSpeed = 1.0f
    private var ktvFontDp = 18f


    companion object {
        const val REQ_AUDIO = 101
        const val REQ_TRACK = 102
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "峻爸 KTV 多文字軌核對器 v1.4"
        setContentView(buildUi())
        handler.post(ticker)
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun TextView.stableTextSize(sizeDp: Float) {
        setTextSize(TypedValue.COMPLEX_UNIT_DIP, sizeDp)
    }

    private fun button(textValue: String, action: () -> Unit): Button =
        Button(this).apply {
            text = textValue
            stableTextSize(14f)
            minHeight = dp(42)
            setPadding(dp(10), 0, dp(10), 0)
            setOnClickListener { action() }
            isAllCaps = false
        }

    private fun horizontalScrollable(row: LinearLayout): HorizontalScrollView =
        HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
            addView(row)
        }

    private fun stableSpinnerAdapter(items: List<String>, sizeDp: Float = 14f): ArrayAdapter<String> =
        object : ArrayAdapter<String>(this, android.R.layout.simple_spinner_item, items) {
            init { setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View =
                super.getView(position, convertView, parent).also {
                    (it as? TextView)?.setTextSize(TypedValue.COMPLEX_UNIT_DIP, sizeDp)
                }
            override fun getDropDownView(position: Int, convertView: View?, parent: ViewGroup): View =
                super.getDropDownView(position, convertView, parent).also {
                    (it as? TextView)?.setTextSize(TypedValue.COMPLEX_UNIT_DIP, sizeDp)
                }
        }

    private fun stableListAdapter(items: List<String>, sizeDp: Float = 13f): ArrayAdapter<String> =
        object : ArrayAdapter<String>(this, android.R.layout.simple_list_item_1, items) {
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View =
                super.getView(position, convertView, parent).also {
                    (it as? TextView)?.setTextSize(TypedValue.COMPLEX_UNIT_DIP, sizeDp)
                }
        }

    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(10), dp(8), dp(10), dp(8))
        }
        root.setOnApplyWindowInsetsListener { view, insets ->
            val top = if (Build.VERSION.SDK_INT >= 30) insets.getInsets(WindowInsets.Type.systemBars()).top else insets.systemWindowInsetTop
            val bottom = if (Build.VERSION.SDK_INT >= 30) insets.getInsets(WindowInsets.Type.systemBars()).bottom else insets.systemWindowInsetBottom
            view.setPadding(dp(10), dp(8) + top, dp(10), dp(8) + bottom)
            insets
        }

        val titleView = TextView(this).apply {
            text = "峻爸 KTV 多文字軌核對器 v1.4｜KTV 精準閱讀版"
            stableTextSize(18f)
            setTextColor(Color.rgb(25, 80, 150))
            setPadding(0, 0, 0, dp(6))
        }
        root.addView(titleView)

        // Audio path stays one compact line.
        val audioRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        audioLabel = TextView(this).apply {
            text = "尚未選擇錄音檔"
            stableTextSize(13f)
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.MIDDLE
            gravity = Gravity.CENTER_VERTICAL
        }
        audioRow.addView(audioLabel, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        audioRow.addView(button("選擇錄音") { openAudio() })
        root.addView(audioRow)

        // Playback controls always stay visible; horizontal scroll avoids squeezing on small phones.
        val playerRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        playerRow.addView(button("▶") { play() })
        playerRow.addView(button("⏸") { player?.pause() })
        playerRow.addView(button("⏹") { stop() })
        playerRow.addView(button("↶5秒") { seekDelta(-5000) })
        playerRow.addView(button("5秒↷") { seekDelta(5000) })
        timeLabel = TextView(this).apply {
            text = "00:00:00 / 00:00:00"
            stableTextSize(13f)
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8), 0, dp(8), 0)
        }
        playerRow.addView(timeLabel)
        val speed = Spinner(this)
        val speeds = listOf("0.75x", "1.0x", "1.25x", "1.5x", "2.0x")
        speed.adapter = stableSpinnerAdapter(speeds, 13f)
        speed.setSelection(1)
        speed.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) {}
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, pos: Int, id: Long) {
                playbackSpeed = listOf(.75f, 1f, 1.25f, 1.5f, 2f)[pos]
                if (Build.VERSION.SDK_INT >= 23) {
                    player?.let { mp ->
                        try {
                            val params = mp.playbackParams
                            params.speed = playbackSpeed
                            mp.playbackParams = params
                        } catch (_: Exception) {
                        }
                    }
                }
            }
        }
        playerRow.addView(speed)
        root.addView(horizontalScrollable(playerRow))

        seek = SeekBar(this).apply {
            max = 1000
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(bar: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (fromUser) {
                        val d = player?.duration ?: 0
                        if (d > 0) player?.seekTo((d * progress / 1000.0).toInt())
                    }
                }

                override fun onStartTrackingTouch(bar: SeekBar?) {}
                override fun onStopTrackingTouch(bar: SeekBar?) {}
            })
        }
        root.addView(seek)

        // Track selectors stay visible; detailed track management opens only when needed.
        val selectRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        activeSpinner = Spinner(this)
        compareSpinner = Spinner(this)
        selectRow.addView(TextView(this).apply { text = "KTV"; stableTextSize(14f); gravity = Gravity.CENTER_VERTICAL })
        selectRow.addView(activeSpinner, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        selectRow.addView(TextView(this).apply { text = "比較"; stableTextSize(14f); gravity = Gravity.CENTER_VERTICAL })
        selectRow.addView(compareSpinner, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(selectRow)

        val toolRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        toolRow.addView(button("☰ 文字軌") { showTrackManager() })
        val topFollowBtn = button("上方KTV：開") { }
        val timelineFollowBtn = button("下方時間軸：開") { }
        topFollowBtn.setOnClickListener {
            topFollow = !topFollow
            topFollowBtn.text = if(topFollow) "上方KTV：開" else "上方KTV：停"
            if(!topFollow) fullText.text = plainFullText else updateViews()
        }
        timelineFollowBtn.setOnClickListener {
            timelineFollow = !timelineFollow
            timelineFollowBtn.text = if(timelineFollow) "下方時間軸：開" else "下方時間軸：停"
            val adapter = timeline.adapter as? TimelineAdapter
            if (!timelineFollow) {
                adapter?.current = -1
                adapter?.notifyDataSetChanged()
            } else {
                currentIndex = -1
                updateViews()
            }
        }
        toolRow.addView(topFollowBtn)
        toolRow.addView(timelineFollowBtn)
        toolRow.addView(button("A−") { changeKtvFont(-1f) })
        toolRow.addView(button("A+") { changeKtvFont(1f) })
        summary = TextView(this).apply {
            text = "尚無文字軌"
            stableTextSize(12f)
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8), 0, dp(6), 0)
        }
        toolRow.addView(summary, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(horizontalScrollable(toolRow))

        currentCue = TextView(this).apply {
            text = "目前：尚未播放"
            stableTextSize(15f)
            setTextColor(Color.rgb(20, 60, 90))
            setBackgroundColor(Color.rgb(225, 240, 250))
            setPadding(dp(10), dp(5), dp(10), dp(5))
            maxLines = 2
            ellipsize = android.text.TextUtils.TruncateAt.END
        }
        root.addView(currentCue)

        val listener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) {}
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, pos: Int, id: Long) {
                rebuild()
            }
        }
        activeSpinner.onItemSelectedListener = listener
        compareSpinner.onItemSelectedListener = listener

        // Main reading area gets almost all remaining height.
        fullText = TextView(this).apply {
            stableTextSize(ktvFontDp)
            setTextColor(Color.DKGRAY)
            setLineSpacing(dp(2).toFloat(), 1.15f)
            setPadding(dp(12), dp(8), dp(12), dp(8))
            setTextIsSelectable(true)
        }
        fullScroll = ScrollView(this).apply {
            addView(fullText)
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.15f)
        }
        root.addView(fullScroll)

        timeline = ListView(this).apply {
            dividerHeight = 1
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f)
        }
        root.addView(timeline)
        timeline.setOnItemClickListener { _, _, pos, _ ->
            val t = activeTrack() ?: return@setOnItemClickListener
            player?.seekTo((t.segments[pos].start * 1000).toInt())
            play()
        }

        return root
    }

    // ---------- Audio / track file pickers ----------
    private fun openAudio() {
        startActivityForResult(
            Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "audio/*"
            },
            REQ_AUDIO
        )
    }

    private fun openTrack() {
        startActivityForResult(
            Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
            },
            REQ_TRACK
        )
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(req: Int, res: Int, data: Intent?) {
        super.onActivityResult(req, res, data)
        if (res != RESULT_OK || data == null) return
        if (req == REQ_AUDIO) {
            data.data?.let { uri ->
                audioUri = uri
                try {
                    contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                } catch (_: Exception) {
                }
                audioLabel.text = TrackParser.displayName(contentResolver, uri)
                preparePlayer(uri)
            }
        }
        if (req == REQ_TRACK) {
            val uris = mutableListOf<Uri>()
            data.clipData?.let { clip ->
                for (i in 0 until clip.itemCount) uris += clip.getItemAt(i).uri
            } ?: data.data?.let { uris += it }
            val oldActive = activeSpinner.selectedItemPosition
            val oldCompare = compareSpinner.selectedItemPosition - 1
            uris.forEach { uri ->
                try {
                    contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                } catch (_: Exception) {
                }
                try {
                    tracks += TrackParser.load(contentResolver, uri)
                } catch (e: Exception) {
                    toast("讀取失敗：${e.message}")
                }
            }
            autoAlign()
            refreshSpinners(oldActive, oldCompare)
        }
    }

    private fun preparePlayer(uri: Uri) {
        player?.release()
        player = MediaPlayer().apply {
            setDataSource(this@MainActivity, uri)
            setOnPreparedListener {
                if (Build.VERSION.SDK_INT >= 23) {
                    try {
                        val params = playbackParams
                        params.speed = playbackSpeed
                        playbackParams = params
                    } catch (_: Exception) {
                    }
                }
                autoAlign()
                updateViews()
            }
            setOnErrorListener { _, _, _ ->
                toast("音訊無法播放")
                true
            }
            prepareAsync()
        }
    }

    private fun play() {
        val p = player
        if (p == null) {
            toast("請先選擇錄音")
            return
        }
        p.start()
    }

    private fun stop() {
        player?.pause()
        player?.seekTo(0)
        updateViews()
    }

    private fun seekDelta(ms: Int) {
        player?.let { it.seekTo((it.currentPosition + ms).coerceIn(0, it.duration)) }
    }

    // ---------- Track management dialog ----------
    private fun showTrackManager() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(10), dp(16), dp(10))
        }
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        row.addView(button("＋ 加入文字／字幕") { openTrack() })
        row.addView(button("自動對齊") { autoAlign(); refreshSpinners() })
        row.addView(button("移除目前 KTV 軌") {
            val i = activeSpinner.selectedItemPosition
            if (i in tracks.indices) {
                tracks.removeAt(i)
                refreshSpinners((i - 1).coerceAtLeast(0), -1)
                toast("已移除文字軌")
            }
        })
        box.addView(horizontalScrollable(row))

        val list = ListView(this)
        val labels = if (tracks.isEmpty()) listOf("目前沒有文字軌") else tracks.mapIndexed { i, t ->
            "${i + 1}. ${t.name}｜${if (t.timed) "有時間軸" else "無時間軸"}｜${if (t.estimated) "估算" else "原始時間碼"}"
        }
        list.adapter = stableListAdapter(labels, 13f)
        list.setOnItemClickListener { _, _, pos, _ ->
            if (pos in tracks.indices) activeSpinner.setSelection(pos)
        }
        box.addView(list, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(220)))
        box.addView(TextView(this).apply {
            text = "提示：DOCX/SRT/VTT 有時間碼時會優先使用；只有單點時間碼的 Word 會自動細分句子並估算句內時間。"
            stableTextSize(12f)
        })

        AlertDialog.Builder(this)
            .setTitle("文字軌管理")
            .setView(box)
            .setPositiveButton("關閉", null)
            .show()
    }

    private fun changeKtvFont(delta: Float) {
        ktvFontDp = (ktvFontDp + delta).coerceIn(14f, 24f)
        fullText.stableTextSize(ktvFontDp)
        (timeline.adapter as? TimelineAdapter)?.let {
            it.bodyTextSizeDp = (ktvFontDp - 2f).coerceAtLeast(12f)
            it.headerTextSizeDp = (ktvFontDp - 5f).coerceAtLeast(10f)
            it.notifyDataSetChanged()
        }
        toast("KTV 字級 ${ktvFontDp.toInt()}")
    }

    private fun activeTrack(): TextTrack? = tracks.getOrNull(activeSpinner.selectedItemPosition)

    private fun compareTrack(): TextTrack? {
        val i = compareSpinner.selectedItemPosition - 1
        return tracks.getOrNull(i)
    }

    private fun refreshSpinners(activeWanted: Int = activeSpinner.selectedItemPosition, compareWanted: Int = compareSpinner.selectedItemPosition - 1) {
        val names = tracks.mapIndexed { index, it -> "[${index+1}] ${it.name}" + if (it.estimated) "（估算）" else "" }
        activeSpinner.adapter = stableSpinnerAdapter(names, 14f)
        compareSpinner.adapter = stableSpinnerAdapter(listOf("不比較") + names, 14f)
        if (tracks.isNotEmpty()) activeSpinner.setSelection(activeWanted.coerceIn(0, tracks.lastIndex))
        compareSpinner.setSelection(if (compareWanted in tracks.indices) compareWanted + 1 else 0)
        rebuild()
    }

    private fun autoAlign() {
        val duration = (player?.duration ?: 0) / 1000.0
        if (duration <= 0) return
        val base = tracks.firstOrNull { it.timed && it.segments.isNotEmpty() }
        tracks.forEach { track ->
            if (!track.timed && track.segments.isNotEmpty()) {
                val texts = track.segments.map { it.text }
                if (base != null) {
                    val joined = texts.joinToString(" ")
                    val n = base.segments.size
                    val step = (joined.length.toDouble() / n).coerceAtLeast(1.0)
                    val newSegments = mutableListOf<Segment>()
                    for (i in 0 until n) {
                        val a = (i * step).toInt().coerceAtMost(joined.length)
                        val b = if (i == n - 1) joined.length else ((i + 1) * step).toInt().coerceAtMost(joined.length)
                        newSegments += Segment(base.segments[i].start, base.segments[i].end, joined.substring(a, b).trim(), "", true)
                    }
                    track.segments = newSegments
                    track.timed = true
                    track.estimated = true
                } else {
                    val weights = texts.map { it.length.coerceAtLeast(1) }
                    val total = weights.sum().toDouble()
                    var current = 0.0
                    track.segments = texts.mapIndexed { i, text ->
                        val span = duration * weights[i] / total
                        val seg = Segment(current, (current + span).coerceAtMost(duration), text, "", true)
                        current += span
                        seg
                    }.toMutableList()
                    if (track.segments.isNotEmpty()) track.segments.last().end = duration
                    track.timed = true
                    track.estimated = true
                }
            }
        }
        rebuild()
    }

    // ---------- KTV / timeline ----------
    private fun rebuild() {
        val track = activeTrack() ?: run {
            fullText.text = ""
            timeline.adapter = null
            summary.text = "尚無文字軌"
            currentCue.text = "目前：尚未播放"
            return
        }
        val compare = compareTrack()
        review = if (compare != null) Review.compare(track, compare) else emptyList()
        val cnt = review.groupingBy { it.level }.eachCount()
        summary.text = if (compare == null) "未比較" else "綠${cnt["green"] ?: 0} 黃${cnt["yellow"] ?: 0} 紅${cnt["red"] ?: 0}（紅=差異）"

        ranges.clear()
        val builder = StringBuilder()
        track.segments.forEach { seg ->
            val start = builder.length
            builder.append(seg.text.trim()).append(" ")
            ranges += start to builder.length
        }
        plainFullText = builder.toString()
        fullText.text = plainFullText
        timeline.adapter = TimelineAdapter(this, track, review, (ktvFontDp - 2f).coerceAtLeast(12f), (ktvFontDp - 5f).coerceAtLeast(10f))
        currentIndex = -1
        updateViews()
    }

    private fun updateViews() {
        val p = player ?: return
        val d = p.duration.coerceAtLeast(0)
        val pos = p.currentPosition.coerceAtLeast(0)
        if (d > 0) seek.progress = (pos * 1000.0 / d).toInt()
        timeLabel.text = "${TrackParser.fmt(pos / 1000.0)} / ${TrackParser.fmt(d / 1000.0)}"
        val track = activeTrack() ?: return
        val now = pos / 1000.0
        val idx = track.segments.indexOfLast { it.start <= now }
        if (idx < 0) return
        val seg = track.segments[idx]
        if (seg.end > seg.start && now > seg.end && idx < track.segments.lastIndex) return
        currentCue.text = "目前 ${TrackParser.fmt(seg.start)}–${TrackParser.fmt(seg.end)}｜${seg.text}"

        if (topFollow) {
            val sb = SpannableStringBuilder(plainFullText)
            if (idx < ranges.size) {
                val (a, b) = ranges[idx]
                sb.setSpan(BackgroundColorSpan(Color.rgb(215, 235, 248)), a, b, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                sb.setSpan(ForegroundColorSpan(Color.rgb(25, 25, 25)), a, b, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                val fraction = ((now - seg.start) / (seg.end - seg.start).coerceAtLeast(.08)).coerceIn(0.0, 1.0)
                val mid = (a + (b - a) * fraction).toInt().coerceIn(a, b)
                if (mid > a) {
                    sb.setSpan(BackgroundColorSpan(Color.rgb(255, 213, 79)), a, mid, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                    sb.setSpan(ForegroundColorSpan(Color.BLACK), a, mid, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)
                }
            }
            fullText.text = sb
        }

        if (idx != currentIndex) {
            currentIndex = idx
            if (timelineFollow) {
                (timeline.adapter as? TimelineAdapter)?.current = idx
                (timeline.adapter as? TimelineAdapter)?.notifyDataSetChanged()
                timeline.setSelection(idx)
            }
            if (topFollow) {
                fullText.post {
                    fullText.layout?.let { layout ->
                        if (idx < ranges.size) {
                            val line = layout.getLineForOffset(ranges[idx].first)
                            val target = (layout.getLineTop(line) - fullScroll.height / 4).coerceAtLeast(0)
                            fullScroll.smoothScrollTo(0, target)
                        }
                    }
                }
            }
        }
    }

    private val ticker = object : Runnable {
        override fun run() {
            updateViews()
            handler.postDelayed(this, 220)
        }
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        player?.release()
        super.onDestroy()
    }
}

class TimelineAdapter(
    private val ctx: android.content.Context,
    private val track: TextTrack,
    private val rev: List<ReviewResult>,
    var bodyTextSizeDp: Float,
    var headerTextSizeDp: Float
) : BaseAdapter() {
    var current = -1
    private fun TextView.dpText(size: Float) = setTextSize(TypedValue.COMPLEX_UNIT_DIP, size)
    override fun getCount() = track.segments.size
    override fun getItem(position: Int) = track.segments[position]
    override fun getItemId(position: Int) = position.toLong()

    override fun getView(position: Int, convertView: View?, parent: ViewGroup?): View {
        val box = (convertView as? LinearLayout) ?: LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(12, 10, 12, 10)
        }
        box.removeAllViews()
        val seg = track.segments[position]
        val result = rev.getOrNull(position)
        val head = TextView(ctx).apply {
            text = "${TrackParser.fmt(seg.start)}–${TrackParser.fmt(seg.end)}  ${seg.speaker}"
            setTextColor(Color.rgb(30, 100, 170))
            dpText(headerTextSizeDp)
        }
        val text = TextView(ctx).apply {
            this.text = seg.text
            dpText(bodyTextSizeDp)
            setTextColor(Color.DKGRAY)
        }
        box.addView(head)
        box.addView(text)
        if (result != null) {
            box.addView(TextView(ctx).apply {
                this.text = "比較：${result.other}"
                dpText((bodyTextSizeDp - 2f).coerceAtLeast(10f))
                setTextColor(Color.GRAY)
            })
            box.addView(TextView(ctx).apply {
                this.text = "● ${(result.score * 100).toInt()}%｜${result.note}"
                dpText((headerTextSizeDp - 1f).coerceAtLeast(9f))
                setTextColor(when(result.level){
                    "green" -> Color.rgb(35,160,75)
                    "yellow" -> Color.rgb(210,150,0)
                    "red" -> Color.rgb(220,60,60)
                    else -> Color.GRAY
                })
            })
        }
        box.setBackgroundColor(if (position == current) Color.rgb(220, 238, 248) else Color.WHITE)
        return box
    }
}
