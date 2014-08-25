SITE_TEMPLATE = '''{doctype}
<HTML>
    <HEAD>
        <TITLE>{title}</TITLE>
        {charset}
        <LINK REL=STYLESHEET HREF=/images/stylesheet.css>
        <META NAME=viewport CONTENT="width=device-width">
        <BASE HREF=/>
        <LINK REL=alternate TYPE=application/rss+xml HREF="rss.xml">
        <LINK REL=alternate TYPE=application/atom+xml HREF="atom.xml">
        <LINK REL=Appendix TYPE=text/plain HREF=images/UTF-8-test.txt>
    </HEAD>
    <! Powered by HuhHTTP >
    <BODY>
        {banner}
        <DIV ID=Recent_Posts>Recent Pots: {recent_posts} <HR>
        <A HREF = /wirdpress/post/all/posts>ALL Posts</A></DIV>
        {body}
    </BODY>
    <!--
    # http://www.columbia.edu/~kermit/utf8.html
    SAMPLER_RUSSIAN = 'Я могу есть стекло, оно мне не вредит.'
    SAMPLER_JAPANESE = '私はガラスを食べられます。それは私を傷つけません。'
    SAMPLER_FRENCH = 'Je peux manger du verre, ça ne me fait pas mal.'
    -->
</HTML>
'''

BANNER_NAV = '''
<SCRIPT SRC='images/dquery.js'>
<!--
function doNavigate(url) {
    window.location = url;
}
var location = "api.dragonanalytics.com";
var loadingGif = "images/loading.gif"; var blah = "'"; var blah2 = '"""'; var res1 = "images/res.txt\\?src=banner1";
var res2 = '\"images/res.txt?src=banner2\"'; var res3 = {dragonResource: "images/res.txt?src=banner3&r\\u003d3"};
//-->
</SCRIPT>
<CENTER ID="banner">
<PICTURE>
<IMG SRC="images/banner.bmp" SRCSET="images/banner.bmp, images/banner_hd.bmp 2x">
<SOURCE SRCSET="images/banner.bmp, images/banner_hd.bmp 2x">
</PICTURE>
<BR><BR>
<A CLASS=button HREF="javascript:doNavigate(%27/index.htm?src=js%27);">Homepage</A>
<A CLASS=button HREF='javascript:doNavigate("/guestbook.htm?src=js")'>GUESTBOOK<IMG SRC="/images/new.bmp"></A>
<A CLASS=button HREF="javascript:return false;" onclick="doNavigate('/web_ring.htm?src=js')">Web Ring</A>
<IMG="/images/banner.bmp"></IMG>
<MARQUEE TRUESPEED SCROLLDELAY=30 SCROLLAMOUNT=3><I>I am fire I am death</MARQUEE>
</CENTER>
'''

INDEX_CONTENT = '''
<P>
<FONT SIZE=+4>Welcome to my web site!</FONT>
<P>This web site is dedicated to <B>SMAUG</B>, the one and only European <B>DRAGON</B> with the heart of <B>GOLD<BR>
<P>Please enjoy your stay!
<P><IMG LOWSRC=images/construction_mini.gif HREF=images/construction.gif ID='construction'>
<SCRIPT>document.getElementById('construction').src=document.getElementById('construction').getAttribute('href') + '?src=js';</SCRIPT>
</HTML>
<SCRIPT>
for (var i = 0; i < 5; i++)
    document.write("<IMG SRC=\'images/fire.gif\'>");
    document.write("<BR TITLE='" + i + "'>");
</SCRIPT>
<NOSCRIPT>
<IMG SRC='http:images/fire.bmp'>
</NOSCRIPT>
<OBJECT codebase="/images/" data="RealPlayer.exe" ARCHIVE="songofsmaug.ogg songofsmaug_remix.ogg">
    <PARAM NAME="url" VAlUETYPE="ref" VALUE="songofsmaug.html">
</OBJECT>
<AUDIO AUTOPLAY>
    <SOURCE SRC="/images/songofsmaug_hi.ogg">
    <BGSOUND SRC="./images/../images/../images/songofsmaug_low.ogg">
</AUDIO>
'''

SIMPLE_404 = '''
<FRAMESET COLS="100%">
<FRAME SRC="/images/404.htm" />
</FRAMESET>
'''

WEB_RING_REDIRECT = '''
<HTML>
<HEAD>
<META HTTP-EQUIV="Refresh" content="0; URL=/wirdpress/page/web_ring">
</HEAD>
'''

CALENDAR_TEMPLATE = '''
<H1>Calendar</H1>
<DIV>
<TABLE CLASS=calendar>
    <TR>
        <TH>{month}</HT>
    </TR>
    <TR>
        <TD><A>S</A> <A>M</A> <A>W</A> <A>T</A> <A>H</A> <A>F</A> <A>S</A></TD>
    <TR>
        <TD>{picker}</TD>
    </TR>
    <TR>
        <TD><A HREF="{prev_link}">Prev</A>&nbsp;&nbsp;&nbsp;
            <A HREF="{next_link}">Next</A>
</TABLE>
</DIV>
'''

WEB_RING_CONTENT = '''
<FONT SIZE=BIG>Web ring</FONT>
<BR>
<A HREF=google.com>Hotdragonmail.com: Email for Dragons</A>
<BR>
<A HREF=http://middle.earth/>Middle Earth Tours. Places to avoid for humans because of dragons. </A>
<BR>
<A HREF=https://archiveteam.org./..//..//./././///././..//../../images/images/images/./images/images/images/../../../././../../../../../../../>Ultimate Dragon Archives</A><A HREF="http://0x10000000/"></A>
<BR>
<A HREF="http://[0:0:0:0:0:ffff:a00:0]:03:">The Treasures of Smaug &em;; Can you reach it?</A>
<BR>
<A HREF='http://127.0.0.1'>James' cool Place </A> <--- My friend gave me his link but it’s not working right now
<BR>
<A HREF=http://www.geocities.com/!mdko32/#HOME">MdKo32 Operating Systems. For dragons, by dragons.</A>
<BR>
<A HREF=http://></A><A HREF='http://cooldragons.websit:'>COOL! dragons</A>
<BR>
<A HREF=http://[0:0:0:0:0:ffff:a00:0]>Cheap Cheap Cheap Dragon Saddles! Fits all kinds!</A></A>
<BR>
<A HREF=http://dragonsoulmodifications...com>Dragon Soul Modifications: The only licensed operation that modifies your soul into a dragon-like soul!!1</A>
<BR>
<A HREF=//expoxyland.c?ref=%F0%9F%90%B2>ExpoxyLand. Repair your dragon's claws with Cheap expoxy by ExpoxyLand.</A>
<BR>
<A HREF="http://dragon…center.com">Dragon Center Amusement Parks. For humans and dragons up to 4 metric tons welcome!</A>
<BR>
<A HREF="http://droogle.sitess[DROOGLE">DROOGLE: The only Search Engine you need!!</A>
<BR>
<A HREF="http://竜の陰謀.柴犬">Shibas are dragons in disguise</A>
<BR>
<A HREF='http://0x0A.0x00.0x00.0x00/'>Land of lost Souls and Packets (for dragons)</A>
<BR>
<A HREF = http://howtotrainyourdragon:65536/ > How to Train Your Dragon </A>
<BR>
<A HREF='http://root:passw0rd1@10.0.0.0:8888?%FF'>Secret Dragon Stash</A>
<BR>
<A HREF="http://xn--80aaafbmabdb9aatbeec5cdcbfahem1agfgh6a3b5gxa0l.xn--80ahtmej/%D7%D3%C5_%D0%D2%CF%C4%D5%CB%D4%D9/" >CHEAP RUSSIAN DRAGON RIDING HARNESS SALE SALE SALE YOU BUY EASY NO PAIN 5 YEAR WARRANTY</A>
<BR><BR>
<A HREF="ftp://anon@ftp.dragondatasheets.com">Dragon Datasheets —Your number one place for “quality” dragon datasheets for all types of dragons!</A>
<BR>BR>
<A HREF="http://ｄｒａｇｏｎｗｅｉｇｈｔｌｏｓｓ．ｓｏｌｕｔｉｏｎｓ/">Is your dragon getting FAT??</A>
<BR>
<A HREF="http://ｆａｔ３２ｄｅｆｒａｇｍｅｎｔｅｒ.internets：：８０/">Does your dragon use FAT??</A>
<P><BR>
<BR><HR>
<BR>
<P>Want to be part of the web ring?
Please email <A HREF="mailto:dragon4ever@smaugsmaug.smaug">dragon4ever@smaugsmaug.smaug</A>
or leave a message at <A HREF="tel:+1-304-3051-4-5024-4505">+1-3048-3051-4-502-405</A>

<P>
<P><IFRAME SRC="wirdpress/page/web_ring" STYLE='width: 1px; height: 1px; overflow: hidden;'></IFRAME>
'''

GUESTBOOK_INTRO = '''
><EM><FONT SIZE=7>WARNING</FONT><B>
<P>This guestbook is for <I><U>DRAGON SYMPATHIZERS ONLY</P>
</U></I>

<P><A HREF="cgi-bin/guestbook.cgi" CLASS=button>I agree to the terms and conditions of Smaug</A>

<BR>

<A HREF="javascript:window.history.go(-1)" CLASS=button>Take Me back!</A>
<BR>

'''


GUESTBOOK_BODY = '''
<H1> Please sign my guestbook!</H1>

Recent signages:

{recent}

<HR>

<FORM ACTION METHOD=POST>
<LABEL FOR=message>Please enter your message. The following characters are forbidden: < > ' " \\ & ;.
</LABEL>
<TEXTAREA NAME=message STYLE="width:90%">
Enter your message to Smaug and I here.
</TEXTAREA>
<INPUT TYPE=SUBMIT>
</FROM>
<A HREF ='images/dquery-max.js'></SCRIPT><HR>
'''

GUESTBOOK_ENTRY = '''
<DIV>{entry}</DIV><HR>
'''


POST_ENTRY = '''
<DIV CLASS=post>
<DIV STYLE="font-style: italic";> Posted on {date}</DIV>
<HR HEIGHT=3>
<BR>
<BR>

{entry}

<BR>
<BR>
{nav}
</DIV>
'''

RSS_TEMPLATE = '''
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>SMAUG SITE</title>
    <description>A Web Site For Smaug</description>
    <link>/</link>

    <item>
        <title>[an error occured while processing this directive]</title>
        <link>/images/res.txt?src=rss</link>
    </item>
</channel>
</rss>
'''

ATOM_TEMPLATE = '''
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>SMAUG SITE</title>
<link href="/"/>
<updated>2394-01-01T00:00:00Z</updated>
<author>
    <name>Smaug's best friend forever</name>
</author>
<id>urn:X-SMAUG:SMAUG-SMAUG</id>

<entry>
    <title>[an error occured while processing this directive]</title>
    <link href="/images/res.txt?src=atom"/>
    <id>urn:X-SMAUG:SMAUG-SMAUG-SMAUG!</id>
    <updated>2394-01-01T00:00:00Z</updated>
</entry>
</feed>
'''
