param(
    [string]$message = "update",
    [string]$tag = ""
)

git add .
git commit -m $message

if ($tag -ne "") {
    git tag -a $tag -m $message
    git push origin $tag
}

git push
