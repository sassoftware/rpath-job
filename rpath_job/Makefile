#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


module = job
SUBDIRS = models

python_files =	__init__.py \
		api1.py \
		$(module)_constants.py

dist_files = Makefile $(module)_constants.py.in $(python_files)

all: default-all $(module)_constants.py default-subdirs

$(module)_constants.py: $(module)_constants.py.in ../Makefile ../Make.defs Makefile
	sed -e s,@version@,$(VERSION),g \
	$< > $@

install: all pyfiles-install default-install install-subdirs pyfiles-compile

dist: default-dist

clean: default-clean
	rm -f $(module)_constants.py

include ../Make.rules
include ../Make.defs
