
content = open('changelog_raw.txt', 'r', encoding='utf-8').read()
lines = content.split('\n')

start_version = '## [1.34.2]'
end_version = '## [1.22.4]'

started = False
extracted = []

for line in lines:
    if line.startswith(start_version):
        started = True
    if line.startswith(end_version):
        break
    if started:
        extracted.append(line)

print('\n'.join(extracted))
