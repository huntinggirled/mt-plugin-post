#!/usr/bin/perl

use strict;
use warnings;
use utf8;

use lib 'lib';
use lib 'extlib';

use MT::Blog;
use MT::Entry;
use MT::Author;
use MT::FileMgr;
use MT::Asset;
use MT::Image;
use MT::WeblogPublisher;
my $publisher = MT::WeblogPublisher->new;

use File::Basename;
use File::Spec;
use Image::Size qw(imgsize);

use CGI;
my $q = new CGI;

print "Content-type: text/plain\n\n";
#print for $q->param;

my $blog_id = $q->param("blogid") or die "load blogid error.";
my $author_id = $q->param("authorid") or die "load author error.";
my $category_id = $q->param("categoryid");
my $title = $q->param("title") or die "load title error.";
my $textbuf = $q->param("text") or die "load text error.";
my ($text, $instadata) = split(/\[instadata\]/, $textbuf);
my @a_file_path = $q->param("filepath");
my $category_id = $q->param("categoryid");
my $status = $q->param("status");

my $blog   = MT::Blog->load($blog_id) or die "load blog error.";
my $author = MT::Author->load($author_id) or die "load author error.";
my $category;
if($category_id) {
    $category = MT::Category->load($category_id) or die "load category error.";
}
my $entry  = MT->model('entry')->new or die "load entry error.";

my $now = time;
my @t = MT::Util::offset_time_list($now, $blog);

my %mime_type_hash = (
	'jpe' => 'image/jpeg',
	'jpg' => 'image/jpeg',
	'jpeg' => 'image/jpeg',
	'png' => 'image/png',
	'gif' => 'image/gif',
   	'mp4' => 'video/mp4',
   	'3gp' => 'video/3gpp',
   	'3g2' => 'video/3gpp2',
);

utf8::decode($title) unless utf8::is_utf8($title);
utf8::decode($text) unless utf8::is_utf8($text);
utf8::decode($instadata) unless utf8::is_utf8($instadata);

$entry->blog_id($blog->id);
$entry->author_id($author->id);
if($status =~ m/^hold/i) {
	$entry->status(MT->model('entry')->HOLD());
} elsif($status =~ m/^release/i) {
	$entry->status(MT->model('entry')->RELEASE());
} else {
	$entry->status($blog->status_default);
}
if($category_id) {
    $entry->category_id($category->id);
}
$entry->allow_comments($blog->allow_comments_default);
$entry->allow_pings($blog->allow_pings_default);
$entry->title($title);
$entry->text($text);
$entry->save or die "entry save error.";
#_save_log("'".$author->name."'がブログ記事「".$title."」(ID:".$entry->id.")を追加しました。", $blog_id, $author_id);
MT->log({
    message => "'".$author->name."'がブログ記事「".$title."」(ID:".$entry->id.")を追加しました。",
    metadata => "エントリーID: ".$entry->id." タイトル: ".$title,
});
for (my $i=0; $i<@a_file_path; $i++) {
	my $file_path = $a_file_path[$i];
	my ($org_basename, $org_dir, $ext) = fileparse($file_path, qr/\.[^.]*/);
	my $fmgr = MT::FileMgr->new('Local') or die MT::FileMgr->errstr;
	my $file_name = sprintf("%d_%d_%d%s", $entry->id, $now, $i, $ext);
	my $absolute_root_path = $blog->site_path;
	my $root_path = '%r/';
	my $root_url = '%r/';
	my $relative_dir = "assets/".sprintf("%04d\/%02d",($t[5]+1900),($t[4]+1))."/";
	my $relative_file_path = $relative_dir.$file_name;
	my $new_file_path = File::Spec->catfile($absolute_root_path, $relative_file_path);
	my $dir = dirname($new_file_path);
	unless($fmgr->exists($dir)) {
		$fmgr->mkpath($dir) or die "dir make error.";
	}
	$fmgr->put($file_path, $new_file_path, 'upload') or die $fmgr->errstr;
	my $asset;
	my $ext_type = $ext;
	$ext_type =~ s/\.//g;
	if($ext_type =~ m/jpe?g|gif|png/) {
		my($width, $height) = imgsize($new_file_path);
		$asset = MT->model('image')->new;
		$asset->label($title);
		$asset->file_path($root_path.$relative_file_path);
		$asset->file_name($file_name);
		$asset->file_ext($ext_type);
		$asset->blog_id($blog->id);
		$asset->created_by($author->id);
		$asset->modified_by($author->id);
		$asset->url($root_url.$relative_file_path);
		$asset->description($instadata);
		$asset->image_width($width);
		$asset->image_height($height);
		$asset->save or die "asset save error.";
	} elsif($ext_type =~ m/mp4|3gp|3g2/) {
		$asset = MT->model('video')->new;
		$asset->label($title);
		$asset->file_path($root_path.$relative_file_path);
		$asset->file_name($file_name);
		$asset->file_ext($ext_type);
		$asset->mime_type($mime_type_hash{$ext_type});
		$asset->blog_id($blog->id);
		$asset->created_by($author->id);
		$asset->modified_by($author->id);
		$asset->url($root_url.$relative_file_path);
		$asset->description($instadata);
		$asset->save or die "asset save error.";
	}
	my $obj_asset = MT->model('objectasset')->new;
	$obj_asset->blog_id($blog->id);
	$obj_asset->asset_id($asset->id);
	$obj_asset->object_ds('entry');
	$obj_asset->object_id($entry->id);
	$obj_asset->save;
	#_save_log("'".$author->name."'がファイル'".$file_name."'(ID:".$asset->id.")を追加しました。", $blog_id, $author_id);
	MT->log({
		message => "'".$author->name."'がファイル'".$file_name."'(ID:".$asset->id.")を追加しました。",
		metadata => "アイテムID: ".$asset->id." ファイル名: ".$file_name,
	});
}
unless($status =~ m/^hold/i) {
	$publisher->rebuild_entry(
		Entry => $entry,
		Blog => $blog,
		BuildDependencies => 1,
	) or die "entry rebuild error.";
	#_save_log("エントリーを再構築しました。".$title, $blog_id, $author_id);
	MT->log({
		message => "エントリーを再構築しました。".$title,
		metadata => "エントリーID: ".$entry->id." タイトル: ".$title,
	});
	MT->run_callbacks( 'scheduled_post_published', MT->instance, $entry, MT->model( 'entry' )->new);
}
print 'OK '.$entry->id;

# sub _save_log {
# 	my ($error_mess,$blog_id,$author_id) = @_;
# 	use MT::Log; 
# 	my $log = MT::Log->new;
# 	$error_mess = 'post.cgi:' . '' . $error_mess;
# 	$log->blog_id($blog_id);
# 	$log->author_id($author_id) if defined $author_id;
# 	$log->message($error_mess);
# 	$log->level(MT::Log::ERROR);
# 	$log->save or die $log->errstr;
# 	return;
# }
